"""AstrBot entry point; domain/storage imports remain independent of this file."""

from astrbot.api import AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, StarTools, register

from .runtime.application import Application


@register("astrbot_plugin_livingemotion", "AKIhunter",
          "Independent source-scoped bot state", "0.1.0")
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
            raw = event.get_extra("livingemotion:context")
            if raw and self.application.config.enabled:
                from .contracts import Context as SourceContext
                exempt = event.get_extra("livingemotion:control_request") in ("wake", "admin")
                availability = await self.application.availability(
                    SourceContext.from_dict(raw), exempt=exempt,
                )
                if availability.block_chat:
                    event.stop_event()
        except Exception:
            # Optional state must not turn normal chat into a host plugin error.
            event.set_extra("livingemotion:unavailable", "state_unavailable")

    @filter.on_llm_request(priority=11000)
    async def supplement_request(self, event: AstrMessageEvent, request: ProviderRequest):
        await self.application.on_llm_request(event, request)

    @filter.on_llm_response(priority=11000)
    async def confirm_consumption(self, event: AstrMessageEvent, response):
        await self.application.mark_request_read(event)

    @filter.command("le_wake", priority=12000)
    async def wake(self, event: AstrMessageEvent):
        # A registered command, not a user-supplied extra/admin JSON field.
        event.set_extra("livingemotion:control_request", "wake")
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
