"""AstrBot entry point; domain/storage imports remain independent of this file."""

import logging
import sys

from astrbot.api import AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, StarTools, register

from .runtime.application import Application
from .runtime.reply_alert import ALERT_ID, ALERT_TEXT, ReplyBlockAlert
from .livinghello_coupling import allowed as coupling_allowed

logger = logging.getLogger(__name__)


def _private_route(event) -> str | None:
    """只在私聊里回告警：群里冒出技术提示会毁掉角色扮演。"""
    umo = getattr(event, "unified_msg_origin", None)
    if not isinstance(umo, str):
        return None
    parts = umo.split(":")
    return umo if len(parts) >= 2 and parts[1] == "FriendMessage" else None


@register("astrbot_plugin_livingemotion", "AKIhunter",
          "Independent source-scoped bot state", "0.2.0")
class LivingEmotionPlugin(Star):
    api_version = 1

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context, config)
        self.application = Application(
            context, config,
            StarTools.get_data_dir("astrbot_plugin_livingemotion"),
        )
        self.api = None
        self.page_api = None
        self.reply_alert = ReplyBlockAlert()

    async def initialize(self) -> None:
        await self.application.initialize()
        self.api = self.application.api
        # Handler ownership is separate; the final page package supplies its F1 guard.
        try:
            from .page_api import PageAPI
        except ImportError:
            return
        self.page_api = PageAPI(self.context, self.application)
        self.page_api.register()

    @filter.event_message_type(filter.EventMessageType.ALL, priority=11000)
    async def observe_message(self, event: AstrMessageEvent):
        # Share only host-authenticated admin status with downstream consumers.
        if event.is_admin() is True:
            event.set_extra("livingemotion:control_request", "admin")
        elif event.get_extra("livingemotion:control_request") == "admin":
            event.set_extra("livingemotion:control_request", None)
        try:
            await self.application.on_message(event)
            if not coupling_allowed(self.context, "livingemotion"):
                return
            raw = event.get_extra("livingemotion:context")
            if raw and self.application.config.enabled:
                from .contracts import Context as SourceContext
                context = SourceContext.from_dict(raw)
                if self.application.effective_mode(context) == "active":
                    # The host reads this before on_llm_request. Buffer the
                    # response so sleep/identity checks run before any output.
                    event.set_extra("enable_streaming", False)
                exempt = event.get_extra("livingemotion:control_request") in ("wake", "admin")
                availability = await self.application.availability(
                    context, exempt=exempt,
                )
                if availability.block_chat:
                    event.stop_event()
        except Exception:
            # Optional state must not turn normal chat into a host plugin error.
            event.set_extra("livingemotion:unavailable", "state_unavailable")

    @filter.on_llm_request(priority=11000)
    async def supplement_request(self, event: AstrMessageEvent, request: ProviderRequest):
        await self.application.on_llm_request(event, request)

    @filter.on_llm_request(priority=-sys.maxsize - 1)
    async def buffer_final_request(self, event: AstrMessageEvent, request: ProviderRequest):
        if not coupling_allowed(self.context, "livingemotion"):
            return
        raw = event.get_extra("livingemotion:context")
        if not raw or self.application.closed or not self.application.config.enabled:
            return
        from .contracts import Context as SourceContext
        if self.application.effective_mode(SourceContext.from_dict(raw)) != "active":
            return
        # Third-party runners read this after the request hooks. Live mode in
        # the native runner always streams and has no guarded submission point.
        event.set_extra("enable_streaming", False)
        if event.get_extra("action_type") == "live":
            event.stop_event()
            event.set_extra("livingemotion:unavailable", "live_submission_unsupported")

    @filter.on_llm_response(priority=11000)
    async def confirm_consumption(self, event: AstrMessageEvent, response):
        if not coupling_allowed(self.context, "livingemotion"):
            return
        await self.application.mark_request_read(event)

    # 必须排在 LivingHello 的发送前复核（priority=-sys.maxsize）之前：
    # 睡前晚安在这时并入 chain，才会被它的分段、表情装饰与逐包投递照常处理。
    # 与下方 submit_reply 同款防御式取钩子：测试桩与旧宿主可能没有这个钩子。
    @getattr(filter, "on_decorating_result", lambda **kw: lambda fn: fn)(
        priority=-sys.maxsize + 1)
    async def merge_closing(self, event: AstrMessageEvent):
        if not coupling_allowed(self.context, "livingemotion"):
            return
        try:
            await self.application.merge_closing_into_reply(event)
        except Exception:
            # 并入失败只放弃晚安本身，绝不能拖垮正常回复的投递。
            logger.warning("[LE-closing] 睡前晚安并入失败", exc_info=True)

    # Runs after LivingHello's last decoration. The time is a host submission
    # boundary; neither this hook nor after-sent proves platform delivery.
    @getattr(filter, "on_decorating_result", lambda **kw: lambda fn: fn)(
        priority=-sys.maxsize - 1)
    async def submit_reply(self, event: AstrMessageEvent):
        if not coupling_allowed(self.context, "livingemotion"):
            return
        outcome = "ok"
        try:
            allowed = await self.application.on_reply_submitted(event)
            if allowed is False:
                outcome = "blocked"
        except Exception:
            # A failed final check cannot authorize a buffered response.
            allowed = False
            outcome = "error"
            event.set_extra("livingemotion:unavailable", "reply_validation_failed")
        if outcome == "blocked":
            # 只有状态机真的拦下回复才计数；校验异常不算「静音」。
            await self._alert_blocked_reply(event)
        elif outcome == "ok":
            self.reply_alert.record_allowed()
        if allowed is False:
            clear = getattr(event, "clear_result", None)
            if callable(clear):
                clear()
            event.stop_event()

    async def _alert_blocked_reply(self, event: AstrMessageEvent) -> None:
        """连续被拦到阈值就提醒一次：日志里留 ID，私聊里回一句话。"""
        if not self.reply_alert.record_blocked():
            return
        logger.warning("%s 连续 %d 次回复被状态机拦截",
                       ALERT_ID, self.reply_alert.threshold)
        route = _private_route(event)
        if route is None:
            return
        try:
            await self.context.send_message(route, self.application.bridge.chain(ALERT_TEXT))
        except Exception:
            logger.warning("%s 告警投递失败", ALERT_ID, exc_info=True)

    @filter.command("le_wake", priority=12000)
    async def wake(self, event: AstrMessageEvent):
        # Deep sleep can only be bypassed by the host's authenticated admin.
        if event.is_admin() is not True:
            return
        event.set_extra("livingemotion:control_request", "admin")
        await self.application.on_message(event)
        raw = event.get_extra("livingemotion:context")
        if raw:
            from .contracts import Context as SourceContext
            await self.application.advance_scope(SourceContext.from_dict(raw), action="night.wake")
        yield event.plain_result("livingEmotion: wake requested")

    async def terminate(self) -> None:
        if self.page_api is not None:
            self.page_api.stop_accepting()
        await self.application.terminate()
