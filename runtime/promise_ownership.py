"""通过宿主公开 cron API 仲裁任务归属，不读取另一系统数据库。"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo

from ..storage.promise_store import normalize

WINDOW_SECONDS = 90.0
RECURRING = re.compile(r"每天|每日|每晚|每周|每星期|每月|每年|每隔|every\s", re.I)


def action_key(text):
    body = normalize(text)
    body = re.sub(
        r"^\s*(?:\d+(?:\.\d+)?\s*(?:分钟|分|小时|秒)(?:后|之后)?|到点了)[，,\s]*", "", body)
    body = re.sub(r"提醒(?:我|他|她|你|用户|对方)?(?:要|去)?", "提醒", body)
    body = re.sub(r"(?:给|发)(?:我|他|她|你|用户|对方)", "", body)
    body = re.sub(r"帮(?:我|他|她|你)", "", body)
    body = re.sub(r"生成(?:一张|张)?|拍(?:一张|张|个)?|发(?:一张|张)?", "", body)
    body = body.replace("照片", "图片").replace("自拍照", "自拍")
    return re.sub(r"\s+", "", body)


def same_action(left, right):
    a, b = action_key(left), action_key(right)
    if not a or not b:
        return False
    return a == b or (min(len(a), len(b)) >= 4
                     and SequenceMatcher(None, a, b).ratio() >= 0.88)


def timestamp(value, timezone_name="UTC"):
    if isinstance(value, (float, int)):
        return float(value)
    if not value:
        return None
    try:
        dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(timezone_name or "UTC"))
        return dt.timestamp()
    except (ValueError, TypeError, KeyError):
        return None


class PromiseOwnership:
    def __init__(self, service):
        self.service, self.app = service, service.app
        self.lock = asyncio.Lock()

    async def host_match(self, context, description, due_at, *, event=None):
        # 同轮工具成功后保存的任务 ID 不依赖模型的最终回复措辞。
        created = (event.get_extra("livingemotion:future_tasks") or []) if event else []
        if len(created) == 1:
            # 契约规定一轮只使用一种调度入口；真实成功回执是来源证据。
            # 同轮只有一个宿主任务时不再猜模型最后那句话的措辞/随机档位。
            return created[0][0]
        mgr = getattr(self.app.host, "cron_manager", None)
        if mgr is None:
            return None
        for job in await mgr.list_jobs(job_type="active_agent"):
            payload = getattr(job, "payload", None)
            if not isinstance(payload, dict):
                continue
            if (not job.enabled or not job.run_once
                    or str(payload.get("session") or "") != context.route
                    or str(payload.get("sender_id") or "") != context.account_id):
                continue
            when = timestamp(payload.get("run_at"), getattr(job, "timezone", None))
            note = str(payload.get("note") or getattr(job, "description", "") or "")
            if (when is not None and abs(when - due_at) <= WINDOW_SECONDS
                    and same_action(description, note)):
                return str(job.job_id)
        for job_id, note, when in created:
            if when is not None and abs(when - due_at) <= WINDOW_SECONDS and same_action(description, note):
                return job_id
        return None

    def wrap_tools(self, event, request):
        original = getattr(request, "func_tool", None)
        if original is None or not bool(getattr(self.app.config, "promise_enabled", True)):
            return
        tool = original.get_tool("future_task")
        if tool is None or getattr(tool, "_livingemotion_ownership", False):
            return
        from astrbot.core.agent.tool import FunctionTool, ToolSet

        owner = self

        class OwnedFutureTask(FunctionTool):
            _livingemotion_ownership = True

            async def call(self, run_context, **kwargs):
                # 周期任务与编辑/删除均由宿主管理，不转换成一次性承诺。
                if (kwargs.get("action") != "create"
                        or not kwargs.get("run_once") or kwargs.get("cron_expression")):
                    return await tool.call(run_context, **kwargs)
                raw = event.get_extra("livingemotion:context")
                if not raw:
                    return await tool.call(run_context, **kwargs)
                from ..contracts import Context

                context = Context.from_dict(raw)
                note = str(kwargs.get("note") or "")
                zone = owner.app.host.get_config(umo=context.route).get("timezone") or "UTC"
                due_at = timestamp(kwargs.get("run_at"), zone)
                if due_at is None or not note.strip():
                    return await tool.call(run_context, **kwargs)
                async with owner.lock:
                    existing = await owner.host_match(context, note, due_at)
                    if existing:
                        owner.record_tool_task(event, existing, note, due_at)
                        return f"Scheduled future task {existing} (already exists)."
                    rows = await owner.service.promises.list(context)
                    matched = [r for r in rows if abs(float(r["due_at"]) - due_at) <= WINDOW_SECONDS
                               and same_action(r["description"], note)]
                    # 已开始执行的 LE 动作不能再创建第二份宿主任务。
                    running = next((r for r in matched if r["status"] == "running"), None)
                    if running:
                        return f"Task already running in LivingEmotion: {running['promise_id']}."
                    result = await tool.call(run_context, **kwargs)
                    match = re.match(r"Scheduled future task (\S+) ", str(result))
                    if not match:
                        return result
                    job_id = match.group(1)
                    owner.record_tool_task(event, job_id, note, due_at)
                    for row in matched:
                        await owner.service.promises.delegate(row["promise_id"], job_id)
                    return result

        wrapped = OwnedFutureTask(
            name=tool.name, description=tool.description, parameters=tool.parameters,
            active=getattr(tool, "active", True),
        )
        tools = ToolSet()
        for item in original.tools:
            tools.add_tool(wrapped if item.name == "future_task" else item)
        request.func_tool = tools

    @staticmethod
    def record_tool_task(event, job_id, note, due_at):
        created = list(event.get_extra("livingemotion:future_tasks") or [])
        item = (job_id, note, due_at)
        if item not in created:
            created.append(item)
        event.set_extra("livingemotion:future_tasks", created)
