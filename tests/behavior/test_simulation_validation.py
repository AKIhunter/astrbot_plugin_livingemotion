"""Simulation accepts only bounded admin fields; no transport framework needed."""
import json
from uuid import uuid4

import pytest

from astrbot_plugin_livingemotion.page_api.errors import ConsoleError
from astrbot_plugin_livingemotion.page_api.routes import PageAPI
from astrbot_plugin_livingemotion.page_api.validation import body_parameters


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


@pytest.mark.asyncio
async def test_optional_legacy_context_and_new_fields():
    assert (await body_parameters("behavior-simulate", Request({})))["context_id"] == ""
    request_id = str(uuid4())
    value = await body_parameters("behavior-simulate", Request({
        "persona_id": "native", "emotion": "anger", "request_id": request_id}))
    assert value == {"context_id": "", "persona_id": "native", "emotion": "anger",
                     "request_id": request_id}
    PageAPI._validate_result("behavior-simulate", {"api_version": 1, "sends": 0}, value)
    with pytest.raises(ConsoleError):
        PageAPI._validate_result("behavior-simulate", {"api_version": 1, "sends": 1}, value)


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"emotion": "invalid"}, {"emotion": []}, {"request_id": "short"},
    {"persona_id": "x" * 513}, {"context_id": 12}, {"target_id": "12345678"},
    {"actor_id": "spoof-admin"}, {"emotion": None},
])
async def test_invalid_body_rejected(payload):
    with pytest.raises(ConsoleError):
        await body_parameters("behavior-simulate", Request(payload))
