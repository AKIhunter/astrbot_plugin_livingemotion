"""Console style-summary draft: one stubbed model call, nothing saved; no network or paid model."""
import asyncio
import json
import re
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.page_api.errors import ConsoleError, public_error
from astrbot_plugin_livingemotion.page_api.routes import PageAPI, ROUTES
from astrbot_plugin_livingemotion.page_api.validation import body_parameters
from astrbot_plugin_livingemotion.runtime import models
from astrbot_plugin_livingemotion.runtime.application import Application, ApplicationError
from astrbot_plugin_livingemotion.runtime.background import ModelResultUnknown
from astrbot_plugin_livingemotion.storage.persona_style import MAX_CHARS
from astrbot_plugin_livingemotion.tests.integration.test_application import Host, NativeConfig, TestBridge

PROMPT = "你是一只说话简短、爱用叠词的猫，称呼对方为「铲屎官」。"
PERSONAS = {"native": PROMPT, "blank": " \n ", "oversized": "设" * 16001, "long": "设" * 3000}
REASON = "控制台自动填写风格摘要"
ROUTE = "verified:adapter:chat"


class Provider:
    def __init__(self, model):
        self.model = model

    def get_model(self):
        return self.model


class Binding:
    """Synthetic budgeted binding: counts UTF-8 bytes like the real ones and records every call."""

    def __init__(self, provider):
        self.provider = provider
        self.fingerprint = provider.model
        self.calls = []
        self.started = asyncio.Event()
        self.release = None
        self.text = "说话简短，常用叠词，语气亲昵。"
        self.error = None

    def count(self, system, data):
        return len(system.encode("utf-8")) + len(data.encode("utf-8")) + 256

    async def generate(self, system, data, output_tokens, timeout):
        self.calls.append((system, data, output_tokens, timeout))
        self.started.set()
        if self.release is not None:
            await self.release.wait()
        if self.error is not None:
            raise self.error
        return self.text


async def make_app(tmp_path, monkeypatch, settings=None):
    host = Host()
    host.default_persona = "native"

    async def get_persona(identifier):
        if identifier not in PERSONAS:
            raise ValueError("Persona does not exist.")
        return SimpleNamespace(system_prompt=PERSONAS[identifier], begin_dialogs=[])

    host.get_persona = get_persona
    providers = {pid: Provider(f"{pid}-model") for pid in ("main", "fallback", "host-default")}
    asked = []

    async def current_chat_provider(route):
        asked.append(route)
        return "host-default"

    host.provider_manager = SimpleNamespace(get_provider_by_id=lambda pid: providers.get(pid))
    host.get_current_chat_provider_id = current_chat_provider
    bindings = {provider.model: Binding(provider) for provider in providers.values()}

    def bind(provider):
        if provider is None:
            raise models.ModelUnavailable("model_unavailable")
        return bindings[provider.model]

    # Only the host provider boundary is synthetic; selection, budgets and errors are real code.
    monkeypatch.setattr(models, "_provider_binding", bind)
    native = NativeConfig({"enabled": False, "mode": "observe_only", "diary_enabled": False,
                           "dream_enabled": False, "persona_mode": "explicit", "persona_id": "native",
                           "timezone": "Asia/Shanghai", **(settings or {})})
    app = Application(host, native, tmp_path, bridge_factory=TestBridge)
    await app.initialize()
    return app, bindings, asked


async def draft(app, persona="native", actor="verified-admin"):
    return await app.console_style_summary_draft(persona, actor_id=actor)


def dispatches(bindings):
    return sum(len(binding.calls) for binding in bindings.values())


async def style_rows(app):
    return await app.store._run(lambda db: db.execute(
        "SELECT COUNT(*) FROM runtime_meta WHERE key LIKE 'console.persona.style.v1:%'").fetchone()[0])


async def test_draft_returns_text_and_only_an_explicit_save_writes(tmp_path, monkeypatch):
    app, bindings, _ = await make_app(tmp_path, monkeypatch, {"provider_id": "main"})
    try:
        result = await draft(app)
        binding = bindings["main-model"]
        assert result == {"api_version": 1, "persona_id": "native", "text": binding.text,
                          "characters": len(binding.text), "available": True, "model": "main-model"}
        # 模型恰好调用一次：输入就是这份人格设定，输出与超时沿用现有预算。
        system, data, output, timeout = binding.calls[0]
        assert data == PROMPT and dispatches(bindings) == 1
        assert "under 2000 characters" in system and "same language" in system
        assert output == app.config.model_output_tokens and timeout == app.config.model_timeout_seconds
        assert await style_rows(app) == 0
        summary = await app.console_style_summary("native")
        assert summary["custom"] is False and summary["text"] == PROMPT
        # 操作者与原因留档：一次付费的手动生成能查到是谁点的。
        audit = await app.store.audit_records()
        assert [(row["action"], row["actor_id"], row["reason_code"]) for row in audit] == [
            ("style_summary.draft", "verified-admin", REASON)]
        assert audit[0]["value"] == {"persona_id": "native", "characters": len(binding.text),
                                     "model": "main-model"}
        await app.console_style_summary_save("native", result["text"], actor_id="verified-admin")
        assert await style_rows(app) == 1
    finally:
        await app.terminate()


async def test_main_model_then_host_default_then_fallback(tmp_path, monkeypatch):
    app, bindings, asked = await make_app(tmp_path, monkeypatch)
    try:
        # 插件通用模型留空：用该人格最近的真实会话向宿主询问当前聊天模型。
        app._contexts["native:chat"] = SimpleNamespace(route=ROUTE, persona_id="native")
        assert (await draft(app))["model"] == "host-default-model"
        assert asked == [ROUTE]
        # 配置了通用模型就不再询问宿主；通用模型失效时退到回退模型。
        asked.clear()
        app.native_config.update(provider_id="main", fallback_provider_id="fallback")
        await app.refresh_config()
        assert (await draft(app))["model"] == "main-model"
        app.native_config.update(provider_id="ghost")
        await app.refresh_config()
        assert (await draft(app))["model"] == "fallback-model"
        assert asked == []
        assert [len(binding.calls) for binding in bindings.values()] == [1, 1, 1]
    finally:
        await app.terminate()


async def test_other_persona_route_and_missing_model_are_unavailable(tmp_path, monkeypatch):
    app, bindings, asked = await make_app(tmp_path, monkeypatch)
    try:
        # 只认同一人格的会话：别的人格的路由不能拿来询问宿主。
        app._contexts["native:chat"] = SimpleNamespace(route=ROUTE, persona_id="other")
        with pytest.raises(ApplicationError) as unavailable:
            await draft(app)
        assert unavailable.value.code == "unavailable"
        assert asked == [] and dispatches(bindings) == 0
        assert await style_rows(app) == 0 and await app.store.audit_records() == []
    finally:
        await app.terminate()


@pytest.mark.parametrize("persona", ["missing", "blank", "oversized"])
async def test_unusable_persona_is_rejected_before_any_model_call(tmp_path, monkeypatch, persona):
    app, bindings, _ = await make_app(tmp_path, monkeypatch, {"provider_id": "main"})
    try:
        with pytest.raises(ApplicationError) as rejected:
            await draft(app, persona)
        assert rejected.value.code == "validation_error" and "人格" in rejected.value.message
        assert dispatches(bindings) == 0 and await app.store.audit_records() == []
    finally:
        await app.terminate()


@pytest.mark.parametrize("fault,code,status,message", [
    ("timeout", "timeout", 504, "模型响应超时（上限 30 秒），没有生成草稿"),
    # 结果未知（上游没给出可用正文）不是超时：分开报，并带上原因码。
    ("unknown", "empty_response", 502, "模型没有返回正文（model_output_invalid，用时 <n> 秒），没有生成草稿"),
    ("provider", "empty_response", 502, "模型没有返回正文（provider_result_unknown，用时 <n> 秒），没有生成草稿"),
    ("crash", "unavailable", 503, "模型生成失败，没有生成草稿"),
    ("blank", "empty_response", 502, "模型没有返回正文（output_unusable，用时 <n> 秒），没有生成草稿"),
    ("nul", "empty_response", 502, "模型没有返回正文（output_unusable，用时 <n> 秒），没有生成草稿"),
])
async def test_model_failure_is_a_clean_error_and_writes_nothing(tmp_path, monkeypatch, fault, code, status, message):
    app, bindings, _ = await make_app(tmp_path, monkeypatch, {"provider_id": "main"})
    binding = bindings["main-model"]
    binding.error = {"timeout": TimeoutError("synthetic provider detail"),
                     "unknown": ModelResultUnknown("model_output_invalid"),
                     "provider": ModelResultUnknown("provider_result_unknown"),
                     "crash": RuntimeError("synthetic crash")}.get(fault)
    binding.text = {"blank": " \n", "nul": "甲\x00乙"}.get(fault, binding.text)
    try:
        with pytest.raises(ApplicationError) as failed:
            await draft(app)
        assert failed.value.code == code and failed.value.status_code == status
        assert re.sub(r"用时 [0-9.]+ 秒", "用时 <n> 秒", failed.value.message) == message
        # 新错误码必须同时登记在公开错误面：状态码对不上会被压回 unavailable，页面又只剩笼统提示。
        public = public_error(failed.value)
        assert (public.code, public.status_code) == (code, status)
        # 上游异常原文不进错误链；日志之外对页面只给稳定错误码。
        assert failed.value.__cause__ is None
        assert len(binding.calls) == 1
        assert await style_rows(app) == 0 and await app.store.audit_records() == []
        # 失败后状态清空：下一次可以正常生成。
        binding.error, binding.text = None, "语气平和。"
        assert (await draft(app))["text"] == "语气平和。" and len(binding.calls) == 2
    finally:
        await app.terminate()


async def test_hanging_model_times_out_and_releases_the_slot(tmp_path, monkeypatch):
    app, bindings, _ = await make_app(tmp_path, monkeypatch,
                                      {"provider_id": "main", "model_timeout_seconds": 1})
    binding = bindings["main-model"]
    binding.release = asyncio.Event()
    try:
        with pytest.raises(ApplicationError) as timed:
            await draft(app)
        assert timed.value.code == "timeout" and timed.value.status_code == 504
        assert timed.value.message == "模型响应超时（上限 1 秒），没有生成草稿"
        assert len(binding.calls) == 1 and await style_rows(app) == 0
        binding.release = None
        assert (await draft(app))["text"] == binding.text
    finally:
        await app.terminate()


async def test_oversized_output_is_cut_to_the_summary_limit(tmp_path, monkeypatch):
    app, bindings, _ = await make_app(tmp_path, monkeypatch, {"provider_id": "main"})
    try:
        bindings["main-model"].text = "字" * (MAX_CHARS + 500) + " \n"
        result = await draft(app)
        assert MAX_CHARS == 2000
        assert result["text"] == "字" * MAX_CHARS and result["characters"] == MAX_CHARS
    finally:
        await app.terminate()


async def test_only_one_generation_at_a_time(tmp_path, monkeypatch):
    app, bindings, _ = await make_app(tmp_path, monkeypatch, {"provider_id": "main"})
    binding = bindings["main-model"]
    binding.release = asyncio.Event()
    try:
        first = asyncio.create_task(draft(app))
        await binding.started.wait()
        with pytest.raises(ApplicationError) as busy:
            await draft(app)
        assert busy.value.code == "generation_in_progress" and busy.value.status_code == 409
        binding.release.set()
        assert (await first)["text"] == binding.text and len(binding.calls) == 1
        binding.release = None
        assert (await draft(app))["text"] == binding.text and len(binding.calls) == 2
    finally:
        await app.terminate()


async def test_stopping_the_plugin_during_generation_discards_the_draft(tmp_path, monkeypatch):
    app, bindings, _ = await make_app(tmp_path, monkeypatch, {"provider_id": "main"})
    binding = bindings["main-model"]
    binding.release = asyncio.Event()
    pending = asyncio.create_task(draft(app))
    await binding.started.wait()
    await app.terminate()
    binding.release.set()
    with pytest.raises(ApplicationError) as stopped:
        await pending
    assert stopped.value.code == "unavailable"
    assert not app._style_summary_draft_lock.locked()


async def test_requires_an_authenticated_actor_and_a_running_plugin(tmp_path, monkeypatch):
    app, bindings, _ = await make_app(tmp_path, monkeypatch, {"provider_id": "main"})
    try:
        with pytest.raises(ApplicationError) as rejected:
            await draft(app, actor="")
        assert rejected.value.code == "validation_error" and dispatches(bindings) == 0
        await app.terminate()
        with pytest.raises(ApplicationError) as stopped:
            await draft(app)
        assert stopped.value.code == "unavailable" and dispatches(bindings) == 0
    finally:
        await app.terminate()


async def test_input_is_cut_to_the_model_input_budget(tmp_path, monkeypatch):
    app, bindings, _ = await make_app(tmp_path, monkeypatch,
                                      {"provider_id": "main", "model_input_tokens": 4096})
    try:
        await draft(app, "long")
        binding = bindings["main-model"]
        system, data, _, _ = binding.calls[0]
        # 按现有输入预算截断：只截人格设定，截到刚好装下，仍是原文前缀。
        assert PERSONAS["long"].startswith(data) and 0 < len(data) < len(PERSONAS["long"])
        # 按字节截断最多丢掉末尾一个汉字：最终占用在预算内，且离预算不超过 3 字节。
        assert 4096 - 3 < binding.count(system, data) <= 4096
    finally:
        await app.terminate()


async def test_budget_too_small_for_the_instruction_is_unavailable(tmp_path, monkeypatch):
    app, bindings, _ = await make_app(tmp_path, monkeypatch,
                                      {"provider_id": "main", "model_input_tokens": 600})
    try:
        with pytest.raises(ApplicationError) as rejected:
            await draft(app)
        assert rejected.value.code == "unavailable" and dispatches(bindings) == 0
    finally:
        await app.terminate()


async def test_reading_the_summary_still_degrades_for_unusable_personas(tmp_path, monkeypatch):
    app, bindings, _ = await make_app(tmp_path, monkeypatch, {"provider_id": "main"})
    try:
        for persona in ("missing", "oversized"):
            assert await app.console_style_summary(persona) == {
                "api_version": 1, "persona_id": persona, "text": "", "characters": 0,
                "custom": False, "available": False}
        present = await app.console_style_summary("native")
        assert present["text"] == PROMPT and present["available"] is True
        assert dispatches(bindings) == 0
    finally:
        await app.terminate()


class Headers:
    def getlist(self, key):
        return []


class Request:
    query = {}
    content_type = "application/json"
    headers = Headers()

    def __init__(self, value):
        self.raw = json.dumps(value).encode()

    async def body(self):
        return self.raw


async def test_transport_accepts_only_a_persona_id():
    assert ("style-summary-draft", "POST") in ROUTES and callable(PageAPI.style_summary_draft)
    assert await body_parameters("style-summary-draft", Request({"persona_id": "native"})) == {
        "persona_id": "native"}
    for payload in ({}, {"persona_id": ""}, {"persona_id": " "}, {"persona_id": "x" * 513},
                    {"persona_id": None}, {"persona_id": 5}, {"persona_id": "a\x00b"},
                    {"persona_id": "native", "actor_id": "forged"},
                    {"persona_id": "native", "text": "x"}, {"persona_id": "native", "reason": "r"}):
        with pytest.raises(ConsoleError) as rejected:
            await body_parameters("style-summary-draft", Request(payload))
        assert rejected.value.code == "validation_error"
