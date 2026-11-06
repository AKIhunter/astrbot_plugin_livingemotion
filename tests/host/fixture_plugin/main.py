"""Independent test fixture, not the livingEmotion implementation."""

import asyncio

from astrbot.api.star import Star, StarTools, register
from astrbot.api.web import error_response, request

from .guard import verified_dashboard_user


@register("livingemotion_host_probe", "local-test", "Isolated contract probe", "0.0.1")
class HostProbe(Star):
    async def initialize(self):
        self.closed = False
        self.data_dir = StarTools.get_data_dir("livingemotion_host_probe")
        self.task = asyncio.create_task(
            asyncio.Event().wait(), name="livingemotion-host-probe"
        )
        self.context.register_web_api(
            "/livingemotion_host_probe/status", self.status, ["GET"], "Probe status"
        )
        self.context.register_web_api(
            "/livingemotion_host_probe/check", self.check, ["POST"], "Probe request"
        )
        self.context.register_web_api(
            "/livingemotion_host_probe/guarded", self.guarded, ["GET", "POST"], "Guard probe"
        )

    async def guarded(self):
        if self.closed or not verified_dashboard_user(self.context):
            return error_response("Dashboard authentication required", status_code=401)
        return {"status": "ok", "data": {"guarded": True}}

    async def status(self):
        return {
            "status": "ok",
            "data": {
                "fixture": True,
                "closed": self.closed,
                "authenticated": bool(request.username),
                "task_active": not self.task.done(),
            },
        }

    async def check(self):
        body = await request.json(default={})
        return {"status": "ok", "data": {"marker": body.get("marker")}}

    async def terminate(self):
        self.closed = True
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)
