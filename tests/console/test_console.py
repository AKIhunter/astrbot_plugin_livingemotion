"""Real host auth/routing/requests with synthetic application output, not core acceptance."""

import asyncio
from dataclasses import asdict
import os
import secrets
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

if not os.environ.get("LIVINGEMOTION_CONSOLE_TEST_ROOT"):
    raise unittest.SkipTest("Run tests/console/run_host_asgi.py in the isolated host venv")

import httpx
import jwt
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers
from starlette.requests import Request

from astrbot.api.web import PluginRequest, bind_request_context
from astrbot.core.star.context import Context
from astrbot.dashboard.api.plugins import legacy_router, router
from astrbot.dashboard.asgi_runtime import DashboardRequestState
from astrbot.dashboard.responses import ApiError
from astrbot.dashboard.server import AstrBotDashboard
from astrbot.dashboard.services.auth_service import AuthService
from astrbot.dashboard.services.auth_service import DASHBOARD_JWT_COOKIE_NAME
from astrbot.dashboard.services.plugin_page_service import PluginPageService

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.page_api import PageAPI
from astrbot_plugin_livingemotion.page_api.errors import ConsoleError
from astrbot_plugin_livingemotion.page_api.guard import require_dashboard_user
from astrbot_plugin_livingemotion.page_api.routes import PLUGIN_NAME
from astrbot_plugin_livingemotion.page_api.validation import ACTIONS, MAX_BODY_BYTES


CONTEXT_ID = "synthetic-authorized"
PREFIXES = (f"/api/plug/{PLUGIN_NAME}", f"/api/v1/plugins/extensions/{PLUGIN_NAME}")
OPERATIONS = ("state", "records", "config", "preview", "action", "scopes", "relationships",
              "relationship", "energy", "settings-options")


def arguments(operation):
    if operation in ("scopes", "relationships", "energy"):
        return "GET", {"params": {"persona_id": "synthetic-persona", "view_scope": "global",
                                  "context_id": CONTEXT_ID}}
    if operation == "settings-options":
        return "GET", {}
    if operation == "relationship":
        return "POST", {"json": {
            "persona_id": "synthetic-persona", "platform": "qq", "account_id": "123",
            "context_id": CONTEXT_ID, "score": 62.1, "expected_version": 0,
            "reason": "Synthetic account correction",
        }}
    if operation == "state":
        return "GET", {"params": {"context_id": CONTEXT_ID}}
    if operation == "records":
        return "GET", {"params": {"context_id": CONTEXT_ID, "kind": "diary"}}
    if operation == "config":
        return "POST", {"json": {
            "context_id": CONTEXT_ID, "expected_revision": "revision-1",
            "patch": {"memory_mode": "local_lite"}, "reason": "Synthetic config check",
        }}
    if operation == "preview":
        return "POST", {"json": {"context_id": CONTEXT_ID}}
    return "POST", {"json": {
        "context_id": CONTEXT_ID, "action": "night.wake",
        "expected_revision": "revision-1", "reason": "Synthetic wake check", "confirmed": True,
    }}


class SyntheticApplication:
    """Only a call-recording port double; no claims of production CAS or persistence."""

    def __init__(self):
        self.calls = []
        self.failure = None
        self.values = asdict(Config())
        self.state = {
            "api_version": 1, "context_id": CONTEXT_ID,
            "contexts": [{"id": CONTEXT_ID, "label": "Synthetic only"}],
            "revision": "revision-1", "mode": "active",
            "config": {"revision": "revision-1", "source": "synthetic native config",
                       "values": self.values, "fields": []},
            "bot_state": {"dimensions": {
                "pleasure": 0.25, "arousal": 0.1, "stress": 0.2, "social_need": 0.3,
            }, "source": "synthetic bot", "expires_at": 1800000000},
            "observation": {"subject": "synthetic-human", "label": "sad",
                            "source": "synthetic human", "expires_at": 1799999999},
            "night": {"energy": 0.75, "reason": "synthetic recovery"},
            "actions": [{"id": item, "enabled": True} for item in sorted(ACTIONS)],
        }
        self.record_rows = [
            {"id": str(index), "body": f"synthetic private entry {index}",
             "source": "synthetic", "expires_at": 1800000000,
             "sources": [{"kind": "human_action", "source_id": f"synthetic-{index}"}]}
            for index in range(23)
        ]
        self.emotion_rows = [
            {"id": str(index), "label": f"synthetic emotion appraisal {index}",
             "before": {"pleasure": 0.5}, "after": {"pleasure": 0.6},
             "source": "synthetic emotion trace", "reason_codes": ["rule_care"]}
            for index in range(23)
        ]

    def check(self, method, parameters):
        self.calls.append((method, parameters))
        if self.failure is not None:
            raise self.failure
        if parameters.get("context_id", "") not in ("", CONTEXT_ID):
            raise ConsoleError("forbidden")

    async def console_state(self, context_id=""):
        self.check("state", {"context_id": context_id})
        return self.state

    async def console_records(self, context_id, kind, page=1, page_size=10, query=""):
        self.check("records", locals_without_self(locals()))
        source = self.emotion_rows if kind == "emotion" else self.record_rows
        rows = [row for row in source if query in row.get("body", row.get("label", ""))]
        return {"api_version": 1, "items": rows[(page - 1) * 10:page * 10],
                "page": page, "page_size": page_size, "total": len(rows)}

    async def update_config(self, patch, *, expected_revision, reason, actor_id, context_id=""):
        self.check("config", locals_without_self(locals()))
        if expected_revision != self.state["config"]["revision"]:
            raise ConsoleError("version_conflict")
        self.values.update(patch)
        self.state["config"]["revision"] = "revision-2"
        return self.state

    async def console_preview(self, context_id):
        self.check("preview", {"context_id": context_id})
        return {"api_version": 1, "eligible": False, "reasons": ["synthetic disabled"],
                "candidates": [], "model_calls": 0, "sends": 0}

    async def console_action(self, context_id, action, *, expected_revision,
                             reason, actor_id, confirmed):
        self.check("action", locals_without_self(locals()))
        return {"api_version": 1, "status": "queued", "request_id": "synthetic-job",
                "reason": "synthetic queued, not a real send"}

    async def console_scopes(self, **parameters):
        self.check("scopes", parameters)
        return {"api_version": 1, "personas": [], "platforms": [], "contexts": [],
                "counts": {"global": 0, "private": 0, "group": 0}}

    async def console_relationships(self, **parameters):
        self.check("relationships", parameters)
        return {"api_version": 1, "nodes": [], "edges": [], "items": [], "total": 0,
                "displayed": 0, "page": parameters["page"], "page_size": 10}

    async def console_relationship(self, **parameters):
        self.check("relationship", parameters)
        if parameters["expected_version"] != 0:
            raise ConsoleError("version_conflict")
        return {"api_version": 1, "version": 1, "node": {
            "platform": parameters["platform"], "account_id": parameters["account_id"],
            "score": parameters["score"], "version": 1}}

    async def console_energy(self, **parameters):
        self.check("energy", parameters)
        return {"api_version": 1, "items": [], "points": [], "total": 0,
                "collected": False, "page": parameters["page"], "page_size": 10}

    async def console_settings_options(self):
        self.check("settings-options", {})
        return {"api_version": 1, "personas": [], "chat_providers": [],
                "embedding_providers": [], "groups": []}


def locals_without_self(values):
    return {key: value for key, value in values.items() if key != "self"}


class HostHarness:
    register_web_api = Context.register_web_api

    def __init__(self):
        self.registered_web_apis = []
        self.config = {"dashboard": {
            "jwt_secret": secrets.token_urlsafe(48), "username": "synthetic-admin",
        }}

    def get_config(self):
        return self.config


class ConsoleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.host = HostHarness()
        self.business = SyntheticApplication()
        self.page = PageAPI(self.host, self.business)
        self.page.register()
        dashboard = object.__new__(AstrBotDashboard)
        dashboard._jwt_secret = self.host.config["dashboard"]["jwt_secret"]
        dashboard.config = self.host.config
        self.app = FastAPI()
        self.app.state.jwt_secret = dashboard._jwt_secret
        self.app.state.db = SimpleNamespace(get_active_api_key_by_hash=AsyncMock(return_value=None))
        self.app.state.core_lifecycle = SimpleNamespace(star_context=self.host)

        @self.app.middleware("http")
        async def native_auth(request, call_next):
            request.state.dashboard_g = DashboardRequestState()
            rejected = await dashboard.auth_middleware(request)
            return rejected if rejected is not None else await call_next(request)

        @self.app.exception_handler(ApiError)
        async def api_error(_request, exc):
            return JSONResponse({"status": "error", "message": exc.message},
                                status_code=exc.status_code)

        self.app.include_router(router, prefix="/api/v1")
        self.app.include_router(legacy_router)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test.invalid",
            trust_env=False,
        )
        self.token = AuthService.generate_jwt(
            SimpleNamespace(config=self.host.config), "synthetic-admin",
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    def issue(self, claims=None, key=None, algorithm="HS256"):
        claims = claims if claims is not None else {
            "username": "synthetic-admin", "exp": time.time() + 3600,
        }
        return jwt.encode(claims, key or self.host.config["dashboard"]["jwt_secret"],
                          algorithm=algorithm)

    async def request(self, prefix, operation, token=None, **override):
        method, kwargs = arguments(operation)
        kwargs.update(override)
        return await self.client.request(
            method, f"{prefix}/console/{operation}",
            headers={"Authorization": f"Bearer {self.token if token is None else token}"},
            **kwargs,
        )

    async def assert_denied_all(self, token, statuses=(401, 403)):
        for prefix in PREFIXES:
            for operation in OPERATIONS:
                with self.subTest(route=prefix, operation=operation):
                    response = await self.request(prefix, operation, token=token)
                    self.assertIn(response.status_code, statuses)
                    self.assertNotIn("synthetic private entry", response.text)
        self.assertEqual(self.business.calls, [])

    async def test_native_dashboard_all_ten_routes_legacy_and_v1(self):
        for prefix in PREFIXES:
            for operation in OPERATIONS:
                with self.subTest(route=prefix, operation=operation):
                    self.business.state["config"]["revision"] = "revision-1"
                    response = await self.request(prefix, operation)
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json()["status"], "ok")
                    self.assertEqual(response.headers["cache-control"], "no-store")
                    self.assertEqual(response.json()["data"]["api_version"], 1)
        self.assertEqual(len(self.business.calls), 20)

    async def test_native_desktop_dashboard_all_ten_routes(self):
        token = AuthService.generate_jwt(
            SimpleNamespace(config=self.host.config), "synthetic-admin", auth_source="desktop",
        )
        for operation in OPERATIONS:
            response = await self.request(PREFIXES[1], operation, token)
            self.assertEqual(response.status_code, 200)

    async def test_native_asset_token_denied_all_private_routes(self):
        token = PluginPageService.issue_plugin_page_asset_token(
            None, plugin_name=PLUGIN_NAME, view_name="livingemotion",
            jwt_secret=self.host.config["dashboard"]["jwt_secret"],
            username="synthetic-admin", locale="zh-CN",
        )
        await self.assert_denied_all(token)
        response = await self.request(PREFIXES[1], "records", token)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.json()["message"].startswith("[livingemotion:forbidden]"))

    async def test_missing_and_query_cookie_apikey_credentials_denied(self):
        for prefix in PREFIXES:
            for operation in OPERATIONS:
                method, kwargs = arguments(operation)
                with self.subTest(route=prefix, operation=operation):
                    response = await self.client.request(
                        method, f"{prefix}/console/{operation}", **kwargs,
                    )
                    self.assertEqual(response.status_code, 401)
            for headers, params in (
                ({}, {"token": self.token, "admin": "true"}),
                ({"Cookie": f"{DASHBOARD_JWT_COOKIE_NAME}={self.token}"}, {}),
                ({"Authorization": "ApiKey synthetic"}, {}),
                ({"X-API-Key": "synthetic"}, {}),
            ):
                with self.subTest(route=prefix, credentials=list(headers)):
                    response = await self.client.get(f"{prefix}/console/state",
                                                     headers=headers, params=params)
                    self.assertIn(response.status_code, (401, 403))
        self.assertEqual(self.business.calls, [])

    async def test_signature_and_expiration_denied_all_private_routes(self):
        for label, token in (
            ("forged", self.issue(key=secrets.token_urlsafe(48))),
            ("expired", self.issue({"username": "synthetic-admin", "exp": time.time() - 100})),
            ("missing_exp", self.issue({"username": "synthetic-admin"})),
            ("wrong_algorithm", self.issue(algorithm="HS384")),
        ):
            with self.subTest(credential=label):
                await self.assert_denied_all(token)

    async def test_oauth_and_unknown_claims_denied_all_private_routes(self):
        for extra in (
            {"token_type": "oauth"}, {"scope": "admin"}, {"sub": "synthetic-admin"},
            {"auth_source": "oauth"}, {"aud": "dashboard"}, {"iss": "external"},
            {"client_id": "synthetic"}, {"admin": True}, {"iat": int(time.time())},
            {"token_type": "dashboard"}, {"auth_source": None},
        ):
            with self.subTest(claim=list(extra)):
                token = self.issue({"username": "synthetic-admin",
                                    "exp": time.time() + 3600, **extra})
                await self.assert_denied_all(token)

    async def test_other_signed_user_is_not_an_administrator(self):
        await self.assert_denied_all(self.issue({
            "username": "synthetic-other", "exp": time.time() + 3600,
        }), (403,))

    async def test_guard_rechecks_signature_identity_and_current_secret(self):
        request = SimpleNamespace(headers=Headers({"Authorization": f"Bearer {self.token}"}),
                                  username="synthetic-admin")
        self.assertEqual(require_dashboard_user(self.host, request), "synthetic-admin")
        request.username = "synthetic-other"
        with self.assertRaises(ConsoleError):
            require_dashboard_user(self.host, request)
        request.username = "synthetic-admin"
        self.host.config["dashboard"]["username"] = "rotated-admin"
        with self.assertRaises(ConsoleError):
            require_dashboard_user(self.host, request)
        self.host.config["dashboard"]["username"] = "synthetic-admin"
        self.host.config["dashboard"]["jwt_secret"] = secrets.token_urlsafe(48)
        with self.assertRaises(ConsoleError):
            require_dashboard_user(self.host, request)
        request.headers = Headers({"Authorization": f"Bearer {self.issue()}"})
        self.assertEqual(require_dashboard_user(self.host, request), "synthetic-admin")

    async def test_guard_malformed_exp_claims_and_duplicate_authorization(self):
        for expires in (True, None, "9999999999", float("nan"), float("inf"), 10**400):
            with self.subTest(exp_type=type(expires).__name__):
                token = self.issue({"username": "synthetic-admin", "exp": expires})
                req = SimpleNamespace(headers=Headers({"Authorization": f"Bearer {token}"}),
                                      username="synthetic-admin")
                with self.assertRaises(ConsoleError):
                    require_dashboard_user(self.host, req)
        for headers in (
            Headers(), Headers({"Authorization": "Bearer " + "x" * 8193}),
            Headers(raw=[(b"authorization", f"Bearer {self.token}".encode()),
                         (b"authorization", f"Bearer {self.token}".encode())]),
        ):
            with self.assertRaises(ConsoleError):
                require_dashboard_user(self.host, SimpleNamespace(
                    headers=headers, username="synthetic-admin",
                ))

    async def test_signed_password_claim_is_supported(self):
        response = await self.request(PREFIXES[1], "state", self.issue({
            "username": "synthetic-admin", "exp": time.time() + 3600,
            "auth_source": "password",
        }))
        self.assertEqual(response.status_code, 200)

    async def test_state_preserves_ui_units_and_separate_observation(self):
        response = await self.request(PREFIXES[1], "state")
        result = response.json()["data"]
        self.assertEqual(result["bot_state"]["dimensions"]["pleasure"], (-0.5 + 1) / 2)
        self.assertEqual(result["night"]["energy"], 75 / 100)
        self.assertEqual(result["observation"]["label"], "sad")
        self.assertEqual(result["bot_state"]["source"], "synthetic bot")
        self.assertEqual(result["observation"]["expires_at"], 1799999999)

    async def test_server_pagination_and_query_are_delegated(self):
        for kind in ("emotion", "behavior", "diary", "dream"):
            for page, count in ((1, 10), (2, 10), (3, 3), (4, 0)):
                response = await self.request(PREFIXES[1], "records", params={
                    "context_id": CONTEXT_ID, "kind": kind, "page": page, "page_size": 10,
                })
                result = response.json()["data"]
                self.assertEqual((len(result["items"]), result["total"]), (count, 23))
                self.assertEqual(result["page_size"], 10)
        response = await self.request(PREFIXES[1], "records", params={
            "context_id": CONTEXT_ID, "kind": "diary", "query": "entry 22",
        })
        self.assertEqual(response.json()["data"]["total"], 1)
        self.assertEqual(self.business.calls[-1][1]["query"], "entry 22")

    async def test_ordinary_emotion_records_never_return_diary_body(self):
        response = await self.request(PREFIXES[1], "records", params={
            "context_id": CONTEXT_ID, "kind": "emotion",
        })
        self.assertEqual(response.status_code, 200)
        items = response.json()["data"]["items"]
        self.assertTrue(all("body" not in item and "appraisal" in item["label"] for item in items))
        self.business.console_records = AsyncMock(return_value={
            "api_version": 1, "items": [{"body": "private diary"}], "total": 1,
            "page": 1, "page_size": 10,
        })
        response = await self.request(PREFIXES[1], "records", params={
            "context_id": CONTEXT_ID, "kind": "emotion",
        })
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private diary", response.text)

    async def test_unknown_context_never_falls_back_to_global_data(self):
        for operation in OPERATIONS:
            if operation == "settings-options":
                continue
            method, kwargs = arguments(operation)
            kwargs["params" if method == "GET" else "json"]["context_id"] = "synthetic-denied"
            response = await self.request(PREFIXES[1], operation, **kwargs)
            self.assertEqual(response.status_code, 403)
            self.assertNotIn("synthetic private entry", response.text)
        self.assertTrue(all(call[1]["context_id"] == "synthetic-denied"
                            for call in self.business.calls))

    async def test_query_whitelist_and_fixed_page_size(self):
        invalid_queries = (
            {"kind": "diary"}, {"context_id": CONTEXT_ID, "kind": "unknown"},
            {"context_id": CONTEXT_ID, "kind": "diary", "page_size": "100"},
            {"context_id": CONTEXT_ID, "kind": "diary", "page_size": "1"},
            {"context_id": CONTEXT_ID, "kind": "diary", "page": "-1"},
            {"context_id": CONTEXT_ID, "kind": "diary", "page": "true"},
            {"context_id": CONTEXT_ID, "kind": "diary", "page": "1000001"},
            {"context_id": CONTEXT_ID, "kind": "diary", "query": "x" * 201},
            {"context_id": CONTEXT_ID, "kind": "diary", "admin": "true"},
            [("context_id", CONTEXT_ID), ("kind", "diary"), ("kind", "dream")],
        )
        for query in invalid_queries:
            with self.subTest(index=invalid_queries.index(query)):
                response = await self.request(PREFIXES[1], "records", params=query)
                self.assertEqual(response.status_code, 400)
        response = await self.request(PREFIXES[1], "state", params={"admin": "true"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.business.calls, [])

    async def test_config_actor_cas_reason_and_no_automatic_retry(self):
        response = await self.request(PREFIXES[1], "config")
        self.assertEqual(response.status_code, 200)
        name, parameters = self.business.calls[-1]
        self.assertEqual(name, "config")
        self.assertEqual(parameters["actor_id"], "synthetic-admin")
        self.assertEqual(parameters["expected_revision"], "revision-1")
        self.assertEqual(parameters["reason"], "Synthetic config check")
        self.assertEqual(parameters["patch"], {"memory_mode": "local_lite"})
        response = await self.request(PREFIXES[1], "config")
        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.json()["message"].startswith("[livingemotion:version_conflict]"))
        self.assertEqual(len(self.business.calls), 2)
        response = await self.request(PREFIXES[1], "state")
        self.assertEqual(response.json()["data"]["config"]["values"]["memory_mode"], "local_lite")

    async def test_invalid_patches_and_admin_actor_forgery_never_reach_core(self):
        for patch in (
            {}, [], {"admin": True}, {"jwt_secret": "synthetic"},
            {"enabled": "true"}, {"enabled": 1}, {"queue_size": True},
            {"mode": []}, {"timezone": None}, {"autonomy_scopes": "x" * 8193},
        ):
            with self.subTest(patch_type=type(patch).__name__):
                body = arguments("config")[1]["json"]
                body["patch"] = patch
                response = await self.request(PREFIXES[1], "config", json=body)
                self.assertEqual(response.status_code, 400)
        for key, value in (("admin", True), ("actor_id", "forged"), ("context", {"admin": True})):
            body = arguments("config")[1]["json"]
            body[key] = value
            response = await self.request(PREFIXES[1], "config", json=body)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.business.calls, [])

    async def test_partial_config_does_not_merge_with_defaults(self):
        self.business.values.update({"persona_id": "synthetic-persona", "wake_at": "09:00"})
        body = arguments("config")[1]["json"]
        body["patch"] = {"persona_mode": "explicit", "sleep_at": "08:00"}
        response = await self.request(PREFIXES[1], "config", json=body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.business.calls[-1][1]["patch"], body["patch"])

    async def test_config_semantic_validation_is_core_owned(self):
        self.business.failure = ConsoleError("validation_error")
        body = arguments("config")[1]["json"]
        body["patch"] = {"queue_size": 1001}
        response = await self.request(PREFIXES[1], "config", json=body)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(self.business.calls), 1)
        self.assertEqual(self.business.values["queue_size"], 100)

    async def test_json_duplicates_nonfinite_size_and_media_type(self):
        for body in (
            b"null", b"[]", b"{", b'{"context_id":"a","context_id":"b"}',
            b'{"patch":{"enabled":true,"enabled":false}}',
            b'{"patch":{"model_daily_limit":NaN}}',
            b'{"patch":{"model_daily_limit":Infinity}}',
            b"[" * 1100 + b"]" * 1100, b"x" * (MAX_BODY_BYTES + 1),
        ):
            with self.subTest(bytes=len(body)):
                response = await self.client.post(
                    f"{PREFIXES[1]}/console/config", content=body,
                    headers={"Authorization": f"Bearer {self.token}",
                             "Content-Type": "application/json"},
                )
                self.assertEqual(response.status_code, 400)
        response = await self.client.post(
            f"{PREFIXES[1]}/console/config", content="{}",
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "text/plain"},
        )
        self.assertEqual(response.status_code, 400)
        response = await self.request(PREFIXES[1], "preview", params={"admin": "true"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.business.calls, [])

    async def test_required_revisions_reasons_confirmation_and_actions(self):
        for operation in ("config", "action"):
            for key, value in (("expected_revision", None), ("expected_revision", True),
                               ("expected_revision", -1), ("expected_revision", ""),
                               ("reason", ""), ("reason", " "), ("reason", "x" * 1001)):
                with self.subTest(operation=operation, field=key, value_type=type(value).__name__):
                    body = arguments(operation)[1]["json"]
                    body[key] = value
                    response = await self.request(PREFIXES[1], operation, json=body)
                    self.assertEqual(response.status_code, 400)
        for key, value in (("confirmed", False), ("confirmed", 1), ("confirmed", "true"),
                           ("action", "relationship.correct"), ("context_id", "")):
            body = arguments("action")[1]["json"]
            body[key] = value
            response = await self.request(PREFIXES[1], "action", json=body)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.business.calls, [])

    async def test_preview_only_uses_pure_port(self):
        response = await self.request(PREFIXES[1], "preview")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["model_calls"], 0)
        self.assertEqual(response.json()["data"]["sends"], 0)
        self.assertEqual(self.business.calls, [("preview", {"context_id": CONTEXT_ID})])

    async def test_each_action_delegates_verified_actor_and_exact_arguments(self):
        for action in sorted(ACTIONS):
            body = arguments("action")[1]["json"]
            body["action"] = action
            response = await self.request(PREFIXES[1], "action", json=body)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["data"]["status"], "queued")
            name, parameters = self.business.calls[-1]
            self.assertEqual(name, "action")
            self.assertEqual(parameters, {**body, "actor_id": "synthetic-admin"})
        self.assertEqual(len(self.business.calls), 5)

    async def test_unwired_action_and_unknown_exceptions_never_claim_success_or_leak(self):
        for exception in (ConsoleError("unavailable"), RuntimeError("synthetic-secret-body")):
            self.business.failure = exception
            response = await self.request(PREFIXES[1], "action")
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("synthetic-secret-body", response.text)
            self.assertIsNone(response.json()["data"])
        self.assertEqual(len(self.business.calls), 2)

    async def test_application_error_structural_port_is_sanitized(self):
        failure = RuntimeError("synthetic-secret")
        failure.code, failure.status_code = "version_conflict", 409
        self.business.failure = failure
        response = await self.request(PREFIXES[1], "config")
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("synthetic-secret", response.text)
        failure.status_code = 200
        response = await self.request(PREFIXES[1], "config")
        self.assertEqual(response.status_code, 503)

    async def test_response_invariants_fail_closed(self):
        for invalid in (
            {"api_version": 1, "page": 1, "page_size": 100, "items": [], "total": 0},
            {"api_version": 1, "page": 1, "page_size": 10, "items": [{}] * 11, "total": 11},
            {"api_version": 1, "page": 1, "page_size": 10, "items": [], "total": -1},
        ):
            self.business.console_records = AsyncMock(return_value=invalid)
            response = await self.request(PREFIXES[1], "records")
            self.assertEqual(response.status_code, 503)
        self.business.console_preview = AsyncMock(return_value={
            "api_version": 1, "model_calls": 1, "sends": 0,
        })
        self.assertEqual((await self.request(PREFIXES[1], "preview")).status_code, 503)
        self.business.console_state = AsyncMock(return_value={"api_version": 1, "x": float("nan")})
        self.assertEqual((await self.request(PREFIXES[1], "state")).status_code, 503)

    async def test_registered_routes_replace_and_old_handlers_stay_closed(self):
        self.page.register()
        self.assertEqual(len(self.host.registered_web_apis), 10)
        self.assertEqual(
            {route for route, *_ in self.host.registered_web_apis},
            {f"/{PLUGIN_NAME}/console/{name}" for name in OPERATIONS},
        )
        self.page.stop_accepting()
        self.page.stop_accepting()
        with self.assertRaises(RuntimeError):
            self.page.register()
        for operation in OPERATIONS:
            self.assertEqual((await self.request(PREFIXES[1], operation)).status_code, 503)
        self.assertEqual(self.business.calls, [])
        replacement = PageAPI(self.host, self.business)
        replacement.register()
        self.assertEqual(len(self.host.registered_web_apis), 10)
        self.assertEqual((await self.request(PREFIXES[1], "state")).status_code, 200)

    async def test_new_relationship_actor_schema_version_and_no_retry(self):
        response = await self.request(PREFIXES[1], "relationship")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.business.calls[-1][1]["actor_id"], "synthetic-admin")
        for key, value in (("actor_id", "forged"), ("expected_version", True),
                           ("score", 10.01), ("score", True), ("score", None),
                           ("score", 10**400), ("frozen", 1), ("persona_id", ""), ("platform", "")):
            body = arguments("relationship")[1]["json"]
            body[key] = value
            response = await self.request(PREFIXES[1], "relationship", json=body)
            self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(len(self.business.calls), 1)
        body = arguments("relationship")[1]["json"]
        body["expected_version"] = 1
        self.assertEqual((await self.request(PREFIXES[1], "relationship", json=body)).status_code, 409)
        self.assertEqual(len(self.business.calls), 2)

    async def test_scope_query_strictness_and_provider_options(self):
        for operation in ("relationships", "energy"):
            for values in ({}, {"persona_id": "p", "view_scope": "public_comment"},
                           {"persona_id": "p", "page_size": 1}, {"persona_id": "p", "admin": True},
                           [("persona_id", "p"), ("platform", "qq"), ("platform", "bilibili")]):
                self.assertEqual((await self.request(PREFIXES[1], operation,
                                                     params=values)).status_code, 400)
        self.assertEqual((await self.request(PREFIXES[1], "energy", params={
            "persona_id": "p", "event_type": "body",
        })).status_code, 400)
        self.assertEqual((await self.request(PREFIXES[1], "settings-options",
                                             params={"secret": "yes"})).status_code, 400)
        self.assertEqual(self.business.calls, [])

    async def test_new_relationship_guard_rechecks_after_body_yield(self):
        async def receive():
            self.host.config["dashboard"]["username"] = "rotated-admin"
            import json
            return {"type": "http.request", "body": json.dumps(
                arguments("relationship")[1]["json"]).encode()}
        raw = Request({
            "type": "http", "method": "POST", "path": "/synthetic",
            "headers": [(b"authorization", f"Bearer {self.token}".encode()),
                        (b"content-type", b"application/json")],
            "query_string": b"", "scheme": "http", "server": ("test.invalid", 80),
        }, receive=receive)
        with bind_request_context(PluginRequest(raw, username="synthetic-admin")):
            response = await self.page.relationship()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.business.calls, [])

    async def test_stop_during_private_read_does_not_release_result(self):
        entered, release = asyncio.Event(), asyncio.Event()

        async def waiting(**_kwargs):
            entered.set()
            await release.wait()
            return self.business.state

        self.business.console_state = waiting
        task = asyncio.create_task(self.request(PREFIXES[1], "state"))
        await entered.wait()
        self.page.stop_accepting()
        release.set()
        self.assertEqual((await task).status_code, 503)

    async def test_revoke_during_private_read_does_not_release_result(self):
        entered, release = asyncio.Event(), asyncio.Event()

        async def waiting(**_kwargs):
            entered.set()
            await release.wait()
            return self.business.state

        self.business.console_state = waiting
        task = asyncio.create_task(self.request(PREFIXES[1], "state"))
        await entered.wait()
        self.host.config["dashboard"]["username"] = "new-synthetic-admin"
        release.set()
        response = await task
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("synthetic-human", response.text)

    async def test_revoke_while_parsing_rejects_before_mutation(self):
        async def receive():
            self.host.config["dashboard"]["jwt_secret"] = secrets.token_urlsafe(48)
            return {"type": "http.request", "body": (
                b'{"context_id":"synthetic-authorized","expected_revision":"revision-1",'
                b'"patch":{"enabled":false},"reason":"synthetic"}'
            )}

        raw = Request({
            "type": "http", "method": "POST", "path": "/synthetic",
            "headers": [(b"authorization", f"Bearer {self.token}".encode()),
                        (b"content-type", b"application/json")],
            "query_string": b"", "scheme": "http", "server": ("test.invalid", 80),
        }, receive=receive)
        with bind_request_context(PluginRequest(raw, username="synthetic-admin")):
            response = await self.page.config()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.business.calls, [])

    async def test_guard_executes_before_parsing_even_with_forged_request_username(self):
        called = False

        async def receive():
            nonlocal called
            called = True
            raise AssertionError("Body must not be read for unauthenticated request")

        raw = Request({
            "type": "http", "method": "POST", "path": "/synthetic",
            "headers": [], "query_string": b"admin=true", "scheme": "http",
            "server": ("test.invalid", 80),
        }, receive=receive)
        req = PluginRequest(raw, username="synthetic-admin")
        with bind_request_context(req):
            response = await self.page.config()
        self.assertEqual(response.status_code, 401)
        self.assertFalse(called)
        self.assertEqual(self.business.calls, [])
