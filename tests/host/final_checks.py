"""Assertions against the installed product; no Application or registry doubles."""

import asyncio
from collections import Counter
import importlib
import json
from pathlib import Path
import secrets
import time

NAME = "astrbot_plugin_livingemotion"
SUFFIX = "<!--livingemotion:state:v1-->"


def product(module):
    return importlib.import_module(f"data.plugins.{NAME}.{module}")


def tasks():
    return [t for t in asyncio.all_tasks()
            if t.get_name().startswith("livingemotion-") and not t.done()]


def plugin(core):
    return core.star_context.get_registered_star(NAME).star_cls


def event(identifier="synthetic-m1", body="synthetic hello"):
    from astrbot.core.platform.astr_message_event import AstrMessageEvent
    from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
    from astrbot.core.platform.message_type import MessageType
    from astrbot.core.platform.platform_metadata import PlatformMetadata
    from astrbot.api.message_components import Plain

    msg = AstrBotMessage()
    msg.type = MessageType.FRIEND_MESSAGE
    msg.self_id = "synthetic-bot"
    msg.message_id = identifier
    msg.message_str = body
    msg.message = [Plain(text=body)]
    msg.sender = MessageMember(user_id="synthetic-human", nickname="synthetic")
    msg.timestamp = time.time()
    return AstrMessageEvent(body, msg, PlatformMetadata(
        name="aiocqhttp", description="Synthetic input; no adapter connected",
        id="synthetic-adapter"), session_id="synthetic-human")


async def setup_persona(core, ev):
    from astrbot.core import sp
    for pid in ("synthetic-persona-a", "synthetic-persona-b"):
        try:
            await core.persona_mgr.get_persona(pid)
        except ValueError:
            await core.persona_mgr.create_persona(
                persona_id=pid, system_prompt=f"Synthetic native persona {pid}.")
    await sp.put_async(scope="umo", scope_id=ev.unified_msg_origin,
                       key="session_service_config", value={"persona_id": "synthetic-persona-a"})


async def seed(core, count=1):
    ev = event()
    await setup_persona(core, ev)
    for i in range(count):
        ev = event(f"synthetic-seed-{i}", "我很难过" if i == 0 else f"synthetic interaction {i}")
        await plugin(core).observe_message(ev)
    return ev


async def basic(core, e, root, *, focus=False):
    from astrbot.api.provider import ProviderRequest
    from astrbot.core import sp

    p = plugin(core)
    e.check("C03.native_data_directory",
            p.application.data_dir == root / "data/plugin_data" / NAME)
    initial_id = p.application.instance_id
    for i in range(3):
        old, owned = plugin(core), tasks()
        ok, _ = await core.plugin_manager.reload(NAME)
        p = plugin(core)
        e.check(f"C03.reload_{i+1}", ok and old is not p and old.application.closed
                and all(t.done() for t in owned) and p.application.instance_id == initial_id)
        counts = Counter(t.get_name() for t in tasks())
        e.check(f"C03.single_task_per_kind_{i+1}", bool(counts) and max(counts.values()) == 1,
                detail=dict(counts))
        e.check(f"C03.ten_routes_{i+1}", sum(
            r[0].startswith("/" + NAME + "/") for r in core.star_context.registered_web_apis) == 10)
    ev = await seed(core, 12)
    raw = ev.get_extra("livingemotion:context")
    e.check("C05.native_event_resolved", bool(raw), fatal=True)
    ctx = product("contracts").Context.from_dict(raw)
    bot_key = product("contracts").stable_key(
        p.application.instance_id, "synthetic-adapter", "aiocqhttp", "qq", "synthetic-bot")
    e.check("C05.bot_persona_separate", ctx.bot_id == bot_key
            and ctx.persona_id == "synthetic-persona-a" and ctx.route == ev.unified_msg_origin)
    req = ProviderRequest(prompt="synthetic input", system_prompt="Synthetic host-owned persona.")
    await p.supplement_request(ev, req)
    await p.supplement_request(ev, req)
    blocks = [x.text for x in req.extra_user_content_parts if getattr(x, "text", "").startswith(SUFFIX)]
    e.check("C08.unique_state_suffix", len(blocks) == 1)
    e.check("C05.native_prompt_not_replaced", req.system_prompt == "Synthetic host-owned persona.")
    state = await p.application.console_state(ctx.account_key)
    records = await p.application.console_records(ctx.account_key, "emotion")
    e.check("C08.trace_and_pagination", records["total"] == 12 and len(records["items"]) == 10
            and "before" in records["items"][0] and "after" in records["items"][0])
    for method in ("get_bot_state", "get_observation", "get_relationship",
                   "get_availability", "preview_behavior"):
        result = await getattr(p.api, method)(ctx)
        e.check(f"C39.{method}", result.get("api_version") == 1 and result.get("status") == "ok",
                detail={k: result.get(k) for k in ("api_version", "status", "reason_code")})
    for method in ("get_capabilities", "get_health"):
        result = await getattr(p.api, method)()
        e.check(f"C39.{method}", result.get("api_version") == 1)
    if focus:
        core._final_synthetic_events = [ev]
        return
    for mode in ("none", "local_lite", "external", "none"):
        p.application.native_config["memory_mode"] = mode
        await p.application.refresh_config()
        current = await p.application.console_state(ctx.account_key)
        e.check(f"C18.mode_{mode}", current["memory"]["mode"] == mode
                and current["relationship"]["raw"] > 0 and "night" in current
                and bool(current["bot_state"]))
        if mode == "external":
            cap = p.application.memory.capabilities()
            e.check("C19.C20.C27.external_explicit_capability_degradation",
                    not cap.background_recall and not cap.append_experience
                    and "external_background_authorization_unsupported" in cap.reason_codes
                    and "external_idempotent_export_unsupported" in cap.reason_codes,
                    detail=product("contracts").to_dict(cap))
            request = product("ports.memory").MemoryRequest("synthetic-background", "diary", ctx)
            recalled = await p.application.memory.recall(request)
            e.check("C21.external_background_returns_no_material", not recalled.materials,
                    detail={"reason_codes": recalled.reason_codes})
            p.application.native_config.update(memory_read=True, memory_export=True)
            await p.application.refresh_config()
            cap = p.application.memory.capabilities()
            request = product("ports.memory").MemoryRequest("synthetic-background-enabled", "diary", ctx)
            recalled = await p.application.memory.recall(request)
            e.check("C19.C20.C21.C27.enabled_external_still_no_background_export",
                    not cap.background_recall and not cap.append_experience and not recalled.materials,
                    detail={"capabilities": product("contracts").to_dict(cap),
                            "recall_reasons": recalled.reason_codes})
            p.application.native_config.update(memory_read=False, memory_export=False)
            await p.application.refresh_config()
    await sp.put_async(scope="umo", scope_id=ev.unified_msg_origin,
                       key="session_service_config", value={"persona_id": "synthetic-persona-b"})
    e.check("C06.old_context_rejected_after_persona_switch",
            not await p.application.validate_context(ctx))
    await p.observe_message(ev)
    newer = product("contracts").Context.from_dict(ev.get_extra("livingemotion:context"))
    e.check("C06.old_state_scope_retained", newer.persona_id == "synthetic-persona-b"
            and newer.account_key != ctx.account_key
            and (await p.api.get_bot_state(ctx))["status"] == "ok")
    await setup_persona(core, ev)
    await p.observe_message(ev)
    ctx = product("contracts").Context.from_dict(ev.get_extra("livingemotion:context"))
    p.application.native_config["mode"] = "observe_only"
    await p.application.refresh_config()
    await p.supplement_request(ev, req)
    e.check("C08.observe_no_injection", not any(
        getattr(x, "text", "").startswith(SUFFIX) for x in req.extra_user_content_parts))
    e.check("C08.observe_no_autonomy", not (await p.application.console_preview(ctx.account_key))["eligible"])
    p.application.native_config["enabled"] = False
    await p.application.refresh_config()
    e.check("C08.disable_stops_business", [t.get_name() for t in tasks()] == ["livingemotion-config"])
    p.application.native_config.update(enabled=True, mode="active", night_enabled=True)
    await p.application.refresh_config()
    sleep = await p.application.advance_scope(ctx, action="night.sleep")
    e.check("C31.manual_sleep_committed", sleep is not None,
            detail={"phase": sleep.phase.value if sleep else None,
                    "context_valid": await p.application.validate_context(ctx)})
    default = await p.api.get_availability(ctx)
    e.check("C31.sleep_default_chat_allowed", default.get("block_chat") is False)
    p.application.native_config["night_block_chat"] = True
    await p.application.refresh_config()
    denied = await p.api.get_availability(ctx)
    e.check("C31.explicit_sleep_blocks", denied.get("block_chat") is True, detail=denied)
    e.check("C31.trusted_exemption", not (await p.application.availability(ctx, exempt=True)).block_chat)
    p.application.native_config.update(night_block_chat=False)
    await p.application.refresh_config()
    await p.application.advance_scope(ctx, action="night.wake")
    p.application.native_config.save_config()
    e.check("C52.normal_chat_zero_configured_models", not core.provider_manager.provider_insts)
    # Retain real synthetic event to preserve the product's weak source reference.
    core._final_synthetic_events = [ev]


async def http_matrix(core, client, token, e, root):
    import jwt
    from astrbot.core import astrbot_config

    p = plugin(core)
    headers = {"Authorization": f"Bearer {token}"}
    bases = [f"/api/plug/{NAME}/console/", f"/api/v1/plugins/extensions/{NAME}/console/"]
    response = await client.get(bases[1] + "state", headers=headers)
    e.check("F1.state_bootstrap", response.status_code == 200, detail=response.status_code, fatal=True)
    state = response.json()["data"]
    context_id = state["context_id"]
    e.check("C44.real_state_available", bool(context_id) and "bot_state" in state, fatal=True)
    page = await client.get(f"/api/v1/plugins/{NAME}/views/livingemotion", headers=headers)
    content_path = page.json().get("data", {}).get("content_path")
    e.check("C04.product_page_discovered", page.status_code == 200 and bool(content_path), fatal=True)
    asset = content_path.split("/_t/", 1)[1].split("/", 1)[0].split("?", 1)[0]
    body = await client.get(content_path)
    e.check("C04.scoped_product_html", body.status_code == 200 and "livingEmotion" in body.text)
    sdk = await client.get("/api/plugin/page/bridge-sdk.js", params={"asset_token": asset})
    e.check("C04.real_bridge_sdk", sdk.status_code == 200 and "AstrBotPluginPage" in sdk.text)
    claims = {"username": "synthetic-final-admin", "exp": int(time.time()) + 600}
    secret = astrbot_config["dashboard"]["jwt_secret"]
    negatives = {
        "anonymous": {},
        "asset": {"Authorization": f"Bearer {asset}"},
        "forged": {"Authorization": "Bearer " + jwt.encode(claims, secrets.token_hex(32), algorithm="HS256")},
        "expired": {"Authorization": "Bearer " + jwt.encode({**claims, "exp": 1}, secret, algorithm="HS256")},
        "oauth": {"Authorization": "Bearer " + jwt.encode({**claims, "token_type": "oauth_access",
                    "scope": "plugins", "sub": "synthetic-user"}, secret, algorithm="HS256")},
        "admin_claim": {"Authorization": "Bearer " + jwt.encode({**claims, "admin": True}, secret,
                                                               algorithm="HS256")},
        "other_user": {"Authorization": "Bearer " + jwt.encode({**claims, "username": "synthetic-guest"},
                                                                secret, algorithm="HS256")},
    }
    methods = {"state": "GET", "records": "GET", "config": "POST",
               "preview": "POST", "action": "POST", "scopes": "GET",
               "relationships": "GET", "relationship": "POST", "energy": "GET",
               "settings-options": "GET"}
    actual_context = (await p.application.store.list_contexts())[0]
    for base in bases:
        route = "legacy" if base.startswith("/api/plug/") else "v1"
        for name, method in methods.items():
            current = (await client.get(base + "state", headers=headers)).json()["data"]
            relations = (await p.application.console_relationships(
                actual_context.persona_id, platform=actual_context.platform))["items"]
            target = next((n for n in relations
                           if n["account_id"] == actual_context.account_id), None)
            payload = {
                "state": {"context_id": context_id},
                "records": {"context_id": context_id, "kind": "emotion", "page": 1, "page_size": 10},
                "config": {"context_id": context_id, "patch": {"memory_mode": "none"},
                           "expected_revision": current["revision"], "reason": "synthetic acceptance"},
                "preview": {"context_id": context_id},
                "action": {"context_id": context_id, "action": "night.wake", "confirmed": True,
                           "expected_revision": current["revision"], "reason": "synthetic acceptance"},
                "scopes": {"persona_id": actual_context.persona_id},
                "relationships": {"persona_id": actual_context.persona_id,
                                  "platform": actual_context.platform},
                "relationship": {"persona_id": actual_context.persona_id,
                                 "platform": actual_context.platform,
                                 "account_id": actual_context.account_id,
                                 "expected_version": target["version"] if target else 0,
                                 "score": 50.1, "reason": "synthetic account acceptance"},
                "energy": {"persona_id": actual_context.persona_id},
                "settings-options": {},
            }[name]
            kwargs = {"params" if method == "GET" else "json": payload}
            positive = await client.request(method, base + name, headers=headers, **kwargs)
            e.check(f"F1.{route}.{name}.administrator", positive.status_code == 200,
                    detail={"status": positive.status_code,
                            "error": positive.json().get("message") if positive.status_code != 200 else None})
            if positive.status_code == 200:
                e.check(f"F1.{route}.{name}.no_store", positive.headers.get("cache-control") == "no-store")
            if name == "state":
                health = (positive.json().get("data") or {}).get("health") or []
                confirmations = [
                    item for item in health
                    if isinstance(item, dict) and item.get("name") == "reply_confirmation"
                ]
                confirmation = confirmations[0] if len(confirmations) == 1 else {}
                e.check(f"F13.{route}.reply_confirmation_unavailable",
                        positive.status_code == 200 and len(confirmations) == 1
                        and confirmation.get("status") == "unavailable",
                        layer="real_host_product_http",
                        detail={"entries": len(confirmations), "status": confirmation.get("status")})
                reason = confirmation.get("reason")
                e.check(f"F13.{route}.reply_confirmation_chinese_reason",
                        isinstance(reason, str) and all(part in reason for part in (
                            "unsupported", "当前宿主无可靠回复确认", "收尾 120 秒超时取消",
                            "不将 after-sent/bool/None 视为发送成功",
                        )),
                        layer="real_host_product_http", detail={"reason": reason})
            for label, auth in negatives.items():
                negative = await client.request(method, base + name, headers=auth, **kwargs)
                e.check(f"F1.{route}.{name}.{label}", negative.status_code in (401, 403),
                        detail=negative.status_code)
            forged_input = {**payload, "admin": True}
            negative = await client.request(method, base + name,
                **{"params" if method == "GET" else "json": forged_input})
            e.check(f"F1.{route}.{name}.admin_input_anonymous", negative.status_code in (401, 403))
    # A page write must persist into the same AstrBotConfig file.
    current = (await client.get(bases[1] + "state", headers=headers)).json()["data"]
    revision = current["revision"]
    body = {"context_id": context_id, "patch": {"memory_mode": "local_lite"},
            "expected_revision": revision, "reason": "synthetic page config"}
    response = await client.post(bases[1] + "config", headers=headers, json=body)
    e.check("C45.page_write_success", response.status_code == 200)
    p = plugin(core)
    native_path = Path(p.application.native_config.config_path)
    e.check("C45.page_write_native_file",
            json.loads(native_path.read_text(encoding="utf-8-sig"))["memory_mode"] == "local_lite")
    stale = await client.post(bases[1] + "config", headers=headers, json=body)
    e.check("C45.stale_revision_409", stale.status_code == 409)
    native_payload = dict(p.application.native_config)
    native_payload["memory_mode"] = "none"
    response = await client.put(f"/api/v1/plugins/{NAME}/config", headers=headers, json=native_payload)
    e.check("C45.native_dashboard_write", response.status_code == 200, detail=response.status_code)
    p = plugin(core)
    await p.observe_message(core._final_synthetic_events[0])
    current = (await client.get(bases[1] + "state", headers=headers)).json()["data"]
    e.check("C45.native_write_reflected_in_console", current["memory"]["mode"] == "none"
            and current["config"]["values"]["memory_mode"] == "none")
    e.check("C45.audit_persisted", len(await p.application.store.audit_records()) >= 2)
    preview = await client.post(bases[1] + "preview", headers=headers,
                                json={"context_id": current["context_id"]})
    e.check("C48.preview_zero_calls_sends", preview.status_code == 200
            and preview.json()["data"]["model_calls"] == preview.json()["data"]["sends"] == 0)


async def stopped(core, e, root):
    from final_run import hashes
    p, owned = plugin(core), tasks()
    old_api, old_page = p.api, p.page_api
    await p.terminate()
    before = hashes(root / "data/plugin_data" / NAME)
    # Include database bytes, not only source extensions.
    def data_hashes():
        import hashlib
        return {str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest()
                for f in (root / "data/plugin_data" / NAME).rglob("*") if f.is_file()}
    before = data_hashes()
    await p.observe_message(event("synthetic-after-stop"))
    await asyncio.sleep(1.2)
    e.check("C03.stop_owned_tasks_done", all(t.done() for t in owned) and not tasks())
    e.check("C03.no_write_after_stop", data_hashes() == before)
    e.check("C03.stopped_api_unavailable", (await old_api.get_capabilities()).get("mode") == "disabled"
            or (await old_api.get_capabilities()).get("status") in ("unavailable", "rejected"))
