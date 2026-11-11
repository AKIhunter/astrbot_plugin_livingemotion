"""真实临时存储与原生保存替身；不调用生产模型或发送端。"""
import asyncio
import json
from dataclasses import replace

import pytest
from urllib.parse import parse_qs

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import to_dict
from astrbot_plugin_livingemotion.domain.relationship import (
    RELATIONSHIP_STAGE_DESCRIPTIONS, relationship_behavior,
)
from astrbot_plugin_livingemotion.page_api.errors import ConsoleError
from astrbot_plugin_livingemotion.page_api.validation import body_parameters, query_parameters
from astrbot_plugin_livingemotion.runtime.console import ApplicationError
from test_management_dto import ConsoleDouble


class QueryParams(dict):
    def __init__(self, value):
        super().__init__(parse_qs(value, keep_blank_values=True))

    def getlist(self, key):
        return self.get(key, [])


class NativeConfig(dict):
    def save_config(self):
        self.saved = dict(self)


class SaveConsole(ConsoleDouble):
    def __init__(self, store, context):
        super().__init__(store, context)
        self._config_lock = asyncio.Lock()
        self.native_config = NativeConfig(to_dict(self.config))
        self.replacements = 0
        self.full_states = 0

    async def _replace_config(self, updated):
        self.config = updated
        self.replacements += 1

    async def console_state(self, context_id=""):
        self.full_states += 1
        return {"api_version": 1, "config": self.config_dto(), "legacy_state": True}


async def test_config_receipt_persists_audit_and_never_reads_full_state(le_store, le_context):
    app = SaveConsole(le_store, le_context)
    before = app.config_revision
    result = await app.update_config(
        {"home_city": "成都", "relationship_stage_descriptions": '["任务可靠","","","主动关心"]'},
        expected_revision=before, reason="", actor_id="synthetic-admin", receipt="config")
    assert set(result) == {"api_version", "config"}
    assert result["config"]["revision"] != before
    assert app.native_config.saved["home_city"] == "成都"
    assert app.replacements == 1 and app.full_states == 0
    rows = await le_store.audit_records()
    assert rows[-1]["action"] == "config.update"
    assert rows[-1]["actor_id"] == "synthetic-admin"
    assert rows[-1]["reason_code"] == "控制台保存配置"
    with pytest.raises(ApplicationError, match="Configuration changed"):
        await app.update_config({"home_city": "北京"}, expected_revision=before,
                                reason="", actor_id="synthetic-admin", receipt="config")
    assert app.native_config.saved["home_city"] == "成都"
    legacy = await app.update_config({"home_city": "上海"}, expected_revision=app.config_revision,
                                    reason="", actor_id="synthetic-admin")
    assert legacy["legacy_state"] and app.full_states == 1


async def test_configuration_read_has_no_full_state_and_validates_scope(le_store, le_context):
    await le_store.register_context(le_context)
    app = SaveConsole(le_store, le_context)
    result = await app.console_configuration(persona_id=le_context.persona_id, view_scope="global")
    assert result["config"]["revision"] == app.config_revision and app.full_states == 0
    with pytest.raises(ApplicationError):
        await app.console_configuration(context_id="unknown-context")
    with pytest.raises(ApplicationError):
        await app.console_configuration(persona_id=le_context.persona_id, view_scope="invalid")


@pytest.mark.parametrize("value", ['[]', '["","",""]', '["","","",1]', '["\\u0000","","",""]',
                                 json.dumps(["x" * 1001, "", "", ""])])
def test_description_limits(value):
    with pytest.raises(ValueError):
        Config(relationship_stage_descriptions=value)


def test_descriptions_match_stages_and_special_note_precedence():
    config = replace(Config(), relationship_stage_descriptions='["可靠完成任务","","更友善","温柔陪伴"]',
                     relationship_special_description="主人，主动关心")
    for index, score in enumerate((0, 110, 250, 450)):
        expected = ("可靠完成任务", RELATIONSHIP_STAGE_DESCRIPTIONS[1], "更友善", "温柔陪伴")[index]
        assert relationship_behavior(score, config)["description"] == expected
    assert relationship_behavior(1000, config)["description"] == "主人，主动关心"
    assert relationship_behavior(1000, config, note="单个对象优先")["description"] == "单个对象优先"


def test_configuration_query_is_bounded_and_legacy_shape_preserved():
    assert query_parameters("configuration", QueryParams("")) == {"context_id": ""}
    assert query_parameters("configuration", QueryParams("persona_id=persona&view_scope=global"))["persona_id"] == "persona"
    with pytest.raises(ConsoleError):
        query_parameters("configuration", QueryParams("persona_id=a&persona_id=b"))


async def test_config_receipt_transport_enum():
    class Request:
        query = {}
        content_type = "application/json"
        headers = QueryParams("")

        async def body(self):
            return json.dumps(self.payload).encode()
    request = Request()
    request.payload = {"expected_revision": "rev", "patch": {"home_city": "成都"}}
    assert "receipt" not in await body_parameters("config", request)
    request.payload["receipt"] = "config"
    assert (await body_parameters("config", request))["receipt"] == "config"
    for invalid in (None, [], {}, "unknown"):
        request.payload["receipt"] = invalid
        with pytest.raises(ConsoleError):
            await body_parameters("config", request)
