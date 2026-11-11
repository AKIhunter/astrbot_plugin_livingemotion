"""Ten product handlers through the real Dashboard, including negative auth."""

import secrets
import time

from retro_common import NAME, ROUTES, plugin, product


async def login(client, password, e):
    response = await client.post("/api/v1/auth/login", json={
        "username": "retro-isolated-admin", "password": password,
    })
    token = response.json().get("data", {}).get("token")
    e.check("http.real_password_login", response.status_code == 200 and bool(token),
            fatal=True)
    return token


async def product_http(core, client, token, e):
    import jwt
    from astrbot.core import astrbot_config
    from retro_reply import observe

    app = plugin(core).application
    # Earlier cases deliberately changed the native session's selected persona.
    # A new real observer establishes a current source for positive writes.
    _, live_context = await observe(
        core, "retro-http-source", "retro-http-persona", app.store.clock(),
    )
    e.check("http.current_native_source", await app.validate_context(live_context), fatal=True)

    auth = {"Authorization": f"Bearer {token}"}
    bases = [
        f"/api/plug/{NAME}/console/",
        f"/api/v1/plugins/extensions/{NAME}/console/",
    ]
    page = await client.get(f"/api/v1/plugins/{NAME}/views/livingemotion", headers=auth)
    content = page.json().get("data", {}).get("content_path")
    e.check("http.product_page_discovery", page.status_code == 200 and bool(content),
            fatal=True)
    asset_token = content.split("/_t/", 1)[1].split("/", 1)[0].split("?", 1)[0]
    response = await client.get(content)
    e.check("http.scoped_html", response.status_code == 200 and "livingEmotion" in response.text)
    response = await client.get("/api/plugin/page/bridge-sdk.js",
                                params={"asset_token": asset_token})
    e.check("http.scoped_bridge_sdk", response.status_code == 200
            and "AstrBotPluginPage" in response.text)
    claims = {"username": "retro-isolated-admin", "exp": int(time.time()) + 600}
    secret = astrbot_config["dashboard"]["jwt_secret"]
    tokens = {
        "anonymous": None,
        "asset_token": asset_token,
        "forged": jwt.encode(claims, secrets.token_hex(32), algorithm="HS256"),
        "expired": jwt.encode({**claims, "exp": 1}, secret, algorithm="HS256"),
        "oauth_typed": jwt.encode(
            {**claims, "token_type": "oauth_access", "scope": "plugins", "sub": "retro-sub"},
            secret, algorithm="HS256",
        ),
        "oauth_untyped_scope": jwt.encode(
            {**claims, "scope": "plugins", "sub": "retro-sub"}, secret, algorithm="HS256",
        ),
        "oauth_auth_source": jwt.encode(
            {**claims, "auth_source": "oauth"}, secret, algorithm="HS256",
        ),
        "admin_claim": jwt.encode({**claims, "admin": True}, secret, algorithm="HS256"),
        "other_user": jwt.encode(
            {**claims, "username": "retro-guest"}, secret, algorithm="HS256",
        ),
    }
    current_response = await client.get(bases[1] + "state", headers=auth)
    e.check("http.state_bootstrap", current_response.status_code == 200, fatal=True)
    current = current_response.json()["data"]
    context_id = current["context_id"]
    e.check("http.selected_live_source", context_id == live_context.account_key, fatal=True)
    selected = current.get("scope_selection") or current.get("selection") or {}
    persona_id = selected.get("persona_id") or (current.get("persona") or {}).get("id")
    e.check("http.native_selected_persona", bool(persona_id), fatal=True)
    selection = {"persona_id": persona_id, "view_scope": "global"}
    rel_response = await client.get(bases[1] + "relationships", headers=auth, params=selection)
    e.check("http.relationship_seed", rel_response.status_code == 200, fatal=True)
    nodes = rel_response.json()["data"]["nodes"]
    e.check("http.relationship_seed_node", bool(nodes), fatal=True)
    for base in bases:
        alias = "legacy" if base.startswith("/api/plug/") else "v1"
        for operation, method in ROUTES.items():
            state = (await client.get(bases[1] + "state", headers=auth)).json()["data"]
            relationship = (await client.get(
                bases[1] + "relationships", headers=auth, params=selection,
            )).json()["data"]["nodes"][0]
            payloads = {
                "state": {"context_id": context_id},
                "records": {"context_id": context_id, "kind": "emotion",
                            "page": 1, "page_size": 10},
                "config": {"context_id": context_id, "patch": {"memory_read": False},
                           "expected_revision": state["revision"], "reason": "Synthetic P8"},
                "preview": {"context_id": context_id},
                "action": {"context_id": context_id, "action": "night.wake",
                           "confirmed": True, "expected_revision": state["revision"],
                           "reason": "Synthetic P8"},
                "scopes": {},
                "relationships": {**selection, "page": 1, "page_size": 10},
                "relationship": {
                    "persona_id": persona_id, "platform": relationship["platform"],
                    "account_id": relationship["account_id"], "score": 42.1,
                    "expected_version": relationship["version"], "reason": "Synthetic P8",
                },
                "energy": {**selection, "page": 1, "page_size": 10},
                "settings-options": {},
            }
            payload = payloads[operation]
            if operation == "config":
                old = await client.post(base + "config", headers=auth, json={
                    **payload, "patch": {"memory_mode": "none"},
                })
                e.check(f"http.{alias}.config.removed_legacy_rejected",
                        old.status_code == 400 and old.json().get("code") ==
                        "validation_error", layer="real_product_dashboard_http")
            kwargs = {"params" if method == "GET" else "json": payload}
            for label, value in tokens.items():
                headers = {} if value is None else {"Authorization": f"Bearer {value}"}
                negative = await client.request(method, base + operation, headers=headers, **kwargs)
                e.check(
                    f"http.{alias}.{operation}.deny_{label}",
                    negative.status_code in (401, 403),
                    detail=negative.status_code, layer="real_product_dashboard_http",
                )
            forged = {**payload, "admin": True, "actor_id": "retro-isolated-admin"}
            negative = await client.request(
                method, base + operation,
                **{"params" if method == "GET" else "json": forged},
            )
            e.check(f"http.{alias}.{operation}.deny_forged_input",
                    negative.status_code in (401, 403), detail=negative.status_code)
            positive = await client.request(method, base + operation, headers=auth, **kwargs)
            e.check(
                f"http.{alias}.{operation}.admin",
                positive.status_code == 200 and positive.json().get("status") == "ok",
                detail={"status": positive.status_code, "code": positive.json().get("code")},
                layer="real_product_dashboard_http",
            )
            e.check(f"http.{alias}.{operation}.no_store",
                    positive.headers.get("cache-control") == "no-store")
            if operation == "preview" and positive.status_code == 200:
                data = positive.json()["data"]
                e.check("http.preview.no_model_or_send", data["model_calls"] == data["sends"] == 0)
            if operation == "settings-options" and positive.status_code == 200:
                data = positive.json()["data"]
                e.check("http.options.no_provider_config", all(
                    set(option) <= {"value", "label"}
                    for kind in ("chat_providers", "embedding_providers")
                    for option in data.get(kind, [])
                ))
            if operation in ("config", "relationship") and positive.status_code == 200:
                replay = await client.request(method, base + operation, headers=auth, **kwargs)
                e.check(f"http.{alias}.{operation}.stale_409",
                        replay.status_code == 409, detail=replay.status_code)
    e.report["http_route_count"] = len(ROUTES)
    e.report["http_alias_count"] = len(bases)
    e.report["http_negative_profiles"] = list(tokens)
    e.check("http.no_native_provider_configuration",
            astrbot_config["provider"] == [])
    Experience = product("contracts").Experience
    app = plugin(core).application
    source = app._context(context_id)
    now = app.store.clock()
    entry = Experience("retro-private-diary", source, "diary", "2026-11-06", now,
                       "日期：2026-11-06\n城市：未配置\n天气：未获取\n我记下一段合成经历。",
                       expires_at=now + 86400)
    seeded = await app.store.save_experience_guarded(
        entry, ((source, await app.store.get_generation(source)),))
    e.check("http.pin.real_store_seed", seeded["status"] == "created", fatal=True)
    for index, base in enumerate(bases):
        payload = {
            "context_id": context_id, "action": "experience.pin",
            "expected_revision": app.revision, "reason": "Synthetic P8 pin",
            "confirmed": True, "entry_id": entry.experience_id,
            "pinned": index == 0, "expected_pinned": index != 0,
        }
        denied = await client.post(base + "action",
                                  headers={"Authorization": f"Bearer {asset_token}"}, json=payload)
        e.check(f"http.pin.{index}.asset_denied", denied.status_code in (401, 403))
        forged = await client.post(base + "action", headers=auth,
                                   json={**payload, "actor_id": "untrusted-input"})
        e.check(f"http.pin.{index}.actor_input_rejected", forged.status_code == 400)
        response = await client.post(base + "action", headers=auth, json=payload)
        data = response.json().get("data") or {}
        e.check(f"http.pin.{index}.updated_without_model",
                response.status_code == 200 and data.get("status") == "updated"
                and data.get("model_calls") == data.get("sends") == 0)
        replay = await client.post(base + "action", headers=auth, json=payload)
        e.check(f"http.pin.{index}.stale_replay_409", replay.status_code == 409)
    stored, _ = await app.store.load_experience(entry.experience_id)
    audit = [row for row in await app.store.audit_records(source)
             if row["action"] == "experience.pin"]
    e.check("http.pin.real_storage_actor_and_original_ttl",
            stored.pinned is False and stored.created_at == now and stored.expires_at == now + 86400
            and len(audit) == 2 and all(row["actor_id"] == "retro-isolated-admin" for row in audit))
    e.check("http.native_config_exists",
            bool(plugin(core).application.native_config.config_path))
