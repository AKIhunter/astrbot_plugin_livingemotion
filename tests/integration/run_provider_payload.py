"""Offline real-provider wire tests. Run with the isolated host Python."""

import argparse
import asyncio
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host-source", type=Path, required=True)
    args = parser.parse_args()
    plugin = Path(__file__).resolve().parents[2]
    sys.path[:0] = [str(args.host_source.resolve()), str(plugin.parent)]
    with tempfile.TemporaryDirectory(prefix="le-provider-test-") as root:
        os.environ["ASTRBOT_ROOT"] = root
        os.chdir(root)
        # All HTTP below uses MockTransport. Accidental real I/O is a hard error.
        def no_network(event, arguments):
            if event in ("socket.connect", "socket.bind", "socket.getaddrinfo", "subprocess.Popen"):
                raise RuntimeError("external I/O forbidden")
        sys.addaudithook(no_network)
        import httpx
        from astrbot.core.provider.sources.openai_source import ProviderOpenAIOfficial
        from astrbot_plugin_livingemotion.runtime.background import ModelResultUnknown
        from astrbot_plugin_livingemotion.runtime.models import ModelUnavailable, OpenAIBinding
        from openai import AsyncOpenAI

        class ProviderTests(unittest.IsolatedAsyncioTestCase):
            async def asyncSetUp(self):
                self.calls = []
                self.status, self.content = 200, "ok"
                self.delay = 0

                async def handler(request):
                    self.calls.append(json.loads(request.content))
                    if self.delay:
                        await asyncio.sleep(self.delay)
                    if self.status != 200:
                        return httpx.Response(self.status, json={"error": {"message": "synthetic"}})
                    if self.content is None:
                        return httpx.Response(200, json={})
                    return httpx.Response(200, json={
                        "id": "synthetic-completion", "object": "chat.completion",
                        "created": 1, "model": "qwen-plus",
                        "choices": [{"index": 0, "finish_reason": "stop",
                                     "message": {"role": "assistant", "content": self.content}}],
                        "usage": {"prompt_tokens": 20, "completion_tokens": 1, "total_tokens": 21},
                    })
                self.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
                client = AsyncOpenAI(api_key="synthetic-not-a-credential",
                                     base_url="https://provider.invalid/v1",
                                     http_client=self.http, max_retries=7)
                self.provider = object.__new__(ProviderOpenAIOfficial)
                self.provider.client = client
                self.provider.provider_config = {
                    "model": "qwen-plus", "custom_extra_body": {
                        "max_tokens": 99999, "max_completion_tokens": 99999,
                        "messages": [{"role": "user", "content": "uncounted"}],
                        "n": 12, "temperature": 0.2,
                    },
                }
                self.provider.api_keys = ["synthetic-key-one", "synthetic-key-two"]
                self.provider.set_model("qwen-plus")
                import inspect
                self.provider.default_params = inspect.signature(
                    client.chat.completions.create,
                ).parameters.keys()
                self.provider.reasoning_key = "reasoning_content"

            async def asyncTearDown(self):
                await self.provider.client.close()

            async def test_qwen_real_payload_is_bounded_and_request_local(self):
                original = copy.deepcopy(self.provider.provider_config)
                original_key = self.provider.client.api_key
                binding = OpenAIBinding(self.provider)
                self.assertEqual(binding.count("system", "中文"), 268)
                self.assertEqual(await binding.generate("system", "中文", 64, 2), "ok")
                self.assertEqual(len(self.calls), 1)
                wire = self.calls[0]
                self.assertEqual(wire["model"], "qwen-plus")
                self.assertEqual(wire["max_tokens"], 64)
                self.assertEqual(wire["n"], 1)
                self.assertFalse(wire["stream"])
                self.assertEqual(len(wire["messages"]), 2)
                self.assertIn("中文", json.dumps(wire["messages"], ensure_ascii=False))
                self.assertNotIn("uncounted", json.dumps(wire))
                self.assertNotIn("max_completion_tokens", wire)
                self.assertNotIn("tools", wire)
                self.assertEqual(self.provider.provider_config, original)
                self.assertEqual(self.provider.client.api_key, original_key)
                self.assertEqual(self.provider.client.max_retries, 7)

            async def test_compatible_non_gpt_model_needs_no_tokenizer(self):
                self.provider.set_model("deployment-alias/qwen3-instruct")
                binding = OpenAIBinding(self.provider)
                self.assertEqual(await binding.generate("rules", "data", 32, 2), "ok")
                self.assertEqual(self.calls[0]["max_tokens"], 32)

            async def test_transient_503_does_not_retry_any_layer(self):
                self.status = 503
                with self.assertRaises(ModelResultUnknown):
                    await OpenAIBinding(self.provider).generate("rules", "data", 32, 2)
                self.assertEqual(len(self.calls), 1)

            async def test_malformed_result_is_unknown_without_retry(self):
                self.content = None
                with self.assertRaises(ModelResultUnknown):
                    await OpenAIBinding(self.provider).generate("rules", "data", 32, 2)
                self.assertEqual(len(self.calls), 1)

            async def test_overlong_output_is_rejected(self):
                self.content = "x" * 33
                with self.assertRaises(ModelResultUnknown):
                    await OpenAIBinding(self.provider).generate("rules", "data", 32, 2)
                self.assertEqual(len(self.calls), 1)

            async def test_timeout_does_not_retry(self):
                self.delay = 1
                with self.assertRaises(TimeoutError):
                    await OpenAIBinding(self.provider).generate("rules", "data", 32, 0.02)
                self.assertEqual(len(self.calls), 1)

            async def test_other_provider_protocol_is_not_silently_accepted(self):
                with self.assertRaises(ModelUnavailable):
                    OpenAIBinding(object())

        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProviderTests)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
