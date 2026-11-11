"""Real native route/auth/lifecycle, temporary SQLite and deterministic model."""
import asyncio
from dataclasses import replace
import json
from uuid import uuid4
from retro_common import NAME, plugin


class DailyModel:
    fingerprint = "daily-synthetic-binding-1"
    def __init__(self):
        self.calls = 0
        self.release = asyncio.Event()
        self.release.set()
        self.started = asyncio.Event()

    def count(self, system, data):
        return len(system.encode()) + len(data.encode())

    async def generate(self, system, data, output, timeout):
        assert output == 8192 and timeout == 90
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return json.dumps({"body": f"我在今日的想象里静静自省。这是合成模型第{self.calls}次。",
                           "source_ids": []}, ensure_ascii=False)


async def daily_http(core, client, token, e):
    app = plugin(core).application
    identifier = "daily-native-persona"
    await core.persona_mgr.create_persona(persona_id=identifier, system_prompt="合成验收人格，不发送消息。")
    app.native_config.update(enabled=False, mode="observe_only", diary_enabled=False,
                             dream_enabled=False, persona_mode="explicit", persona_id=identifier,
                             timezone="Asia/Shanghai", model_daily_limit=1, home_city="")
    app.native_config.save_config()
    await app.refresh_config()
    model = DailyModel()
    async def binding(kind):
        return model
    app.manual_model_binding = binding
    e.check("daily.no_live_sources", not app._contexts)
    auth = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/plugins/extensions/{NAME}/console/"
    page = await client.get(f"/api/v1/plugins/{NAME}/views/livingemotion", headers=auth)
    content = page.json()["data"]["content_path"]
    asset_token = content.split("/_t/", 1)[1].split("/", 1)[0].split("?", 1)[0]
    for operation, method, body in [
        ("experience-generate", "POST", {"request_id": str(uuid4()), "persona_id": identifier, "kind": "diary"}),
        ("experience-task", "GET", {"request_id": str(uuid4())}),
    ]:
        for credential in [None, asset_token, "forged-token"]:
            headers = {} if credential is None else {"Authorization": f"Bearer {credential}"}
            response = await client.request(method, base + operation, headers=headers,
                                            **({"json": body} if method == "POST" else {"params": body}))
            e.check(f"daily.{operation}.denied.{credential is None}.{credential == asset_token}",
                    response.status_code in (401, 403))
    e.check("daily.auth_no_dispatch", model.calls == 0)
    state = await client.get(base + "state", headers=auth)
    e.check("daily.no_event_enabled_actions", state.status_code == 200 and
            all(a["enabled"] for a in state.json()["data"]["actions"]
                if a["id"] in ("diary.generate", "dream.generate")), fatal=True)
    wrong = await client.post(base + "experience-generate", headers=auth, json={
        "request_id": str(uuid4()), "persona_id": "other", "kind": "diary"})
    e.check("daily.persona_conflict", wrong.status_code == 409)
    invalid = await client.post(base + "experience-generate", headers=auth, json={
        "request_id": str(uuid4()), "persona_id": identifier, "kind": "diary", "day": "yesterday"})
    e.check("daily.server_date_only", invalid.status_code == 400)
    first = None
    for kind in ("diary", "diary", "dream"):
        body = {"request_id": str(uuid4()), "persona_id": identifier, "kind": kind}
        response = await client.post(base + "experience-generate", headers=auth, json=body)
        e.check(f"daily.{kind}.accepted.{model.calls}", response.status_code == 200, fatal=True)
        await asyncio.wait_for(app.manual_experience.queue.join(), 3)
        task = await client.get(base + "experience-task", headers=auth,
                                params={"request_id": body["request_id"]})
        result = task.json()["data"]
        e.check(f"daily.{kind}.stored.{model.calls}", result["status"] == "succeeded" and
                result["timezone"] == "Asia/Shanghai", fatal=True)
        if first is None:
            first = result["experience_id"]
            old, generation = await app.store.load_experience(first)
            await app.store.pin_experience(old, replace(old, pinned=True), generation,
                                           actor_id="test", reason="native synthetic pin")
        elif kind == "diary":
            saved, _ = await app.store.load_experience(result["experience_id"])
            e.check("daily.overwrite_pin_stable", result["experience_id"] == first and saved.pinned)
        e.check("daily.no_store_cache", task.headers.get("cache-control") == "no-store")
    e.check("daily.only_three_dispatches", model.calls == 3)
    e.check("daily.two_types_one_each", all([
        (await app.console_records(kind=k, persona_id=identifier))["total"] == 1
        for k in ("diary", "dream")]))
    e.check("daily.no_private_routes", all(c.platform != "console" for c in app._contexts.values()))
    e.report["daily_synthetic_model_calls"] = model.calls
    e.report["daily_scope"] = "focused native HTTP + actual iframe, not four-version full regression"
    # Keep this deterministic model in the isolated host for genuine iframe clicks.
    app._daily_native_model = model
