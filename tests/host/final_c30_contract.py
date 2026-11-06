"""C30 host contract probe; real host classes, synthetic listener and transport.

No product is loaded here. This proves what the fixed host hook can observe,
not that LivingEmotion has a working success-receipt integration.
"""

import argparse
import asyncio
from collections import Counter
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback
from types import SimpleNamespace

from run_isolated_host import guard_network


HEAD = "61335414433db721b3f7ecc93f90deafe0a59d78"
HOST_FILES = (
    "astrbot/core/pipeline/respond/stage.py",
    "astrbot/core/pipeline/context_utils.py",
    "astrbot/core/platform/astr_message_event.py",
    "astrbot/core/platform/sources/aiocqhttp/aiocqhttp_message_event.py",
    "astrbot/core/star/context.py",
    "astrbot/core/star/star_handler.py",
)


def verify_host(root):
    # This task uses one detached checkout and does not invoke Git.
    if (root / ".git/HEAD").read_text().strip() != HEAD:
        raise ValueError("Expected the fixed detached host HEAD")


async def probe(report):
    from astrbot.core import astrbot_config
    from astrbot.core.message.components import Plain
    from astrbot.core.message.message_event_result import MessageEventResult
    from astrbot.core.pipeline.respond.stage import RespondStage
    from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
    from astrbot.core.platform.message_type import MessageType
    from astrbot.core.platform.platform_metadata import PlatformMetadata
    from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
        AiocqhttpMessageEvent,
    )
    from astrbot.core.star.star import StarMetadata, star_map
    from astrbot.core.star.star_handler import (
        EventType, StarHandlerMetadata, star_handlers_registry,
    )

    def check(name, value):
        report["checks"].append({"name": name, "passed": bool(value),
                                "layer": "real_host_contract_synthetic_transport_listener"})

    observed = []

    async def after_sent(event):
        observed.append({
            "has_send": event._has_send_oper,
            "incoming_message_id": event.message_obj.message_id,
            "extra_keys": sorted(event.get_extra()),
            "result_present": event.get_result() is not None,
        })

    module = "final_c30_synthetic_listener"
    handler = StarHandlerMetadata(
        event_type=EventType.OnAfterMessageSentEvent,
        handler_full_name=module + ".after_sent",
        handler_name="after_sent", handler_module_path=module,
        handler=after_sent, event_filters=[],
    )
    star_map[module] = StarMetadata(name=module, activated=True)
    star_handlers_registry.append(handler)

    class Transport:
        def __init__(self, outcomes):
            self.outcomes = iter(outcomes)
            self.calls = 0
            self.acknowledged = 0

        async def send_private_msg(self, **kwargs):
            self.calls += 1
            outcome = next(self.outcomes)
            if isinstance(outcome, BaseException):
                raise outcome
            if isinstance(outcome, dict) and outcome.get("message_id"):
                self.acknowledged += 1
            return outcome

    config = copy.deepcopy(dict(astrbot_config))
    config["platform_settings"]["segmented_reply"].update(
        enable=False, only_llm_result=False, interval_method="fixed", interval="0,0")

    def event(transport):
        msg = AstrBotMessage()
        msg.type = MessageType.FRIEND_MESSAGE
        msg.self_id = "100001"
        msg.message_id = "synthetic-incoming"
        msg.sender = MessageMember(user_id="100002", nickname="synthetic")
        msg.message_str = "synthetic input"
        msg.message = [Plain(text=msg.message_str)]
        msg.timestamp = time.time()
        return AiocqhttpMessageEvent(
            msg.message_str, msg,
            PlatformMetadata(name="aiocqhttp", description="synthetic transport",
                             id="synthetic-instance"),
            session_id="100002", bot=transport)

    cases = (
        ("ack", [{"message_id": 100003}], False, 1, True),
        ("none", [None], False, 0, True),
        ("false", [False], False, 0, True),
        ("exception", [RuntimeError("synthetic send failure")], False, 0, False),
        ("timeout", [TimeoutError("synthetic unknown outcome")], False, 0, False),
        ("partial", [{"message_id": 100003}, RuntimeError("synthetic second failure")],
         True, 1, True),
        ("all_failed", [RuntimeError("synthetic first failure"),
                        RuntimeError("synthetic second failure")], True, 0, False),
        ("cancelled", [asyncio.CancelledError()], False, 0, False),
    )
    try:
        for label, outcomes, segmented, acknowledgements, has_send in cases:
            observed.clear()
            transport = Transport(outcomes)
            ev = event(transport)
            cfg = copy.deepcopy(config)
            cfg["platform_settings"]["segmented_reply"]["enable"] = segmented
            stage = RespondStage()
            await stage.initialize(SimpleNamespace(astrbot_config=cfg))
            chain = [Plain(text="Synthetic response.")]
            if segmented:
                chain.append(Plain(text="Synthetic second segment."))
            ev.set_result(MessageEventResult(chain=chain))
            cancelled = False
            try:
                await stage.process(ev)
            except asyncio.CancelledError:
                cancelled = True
            expected_hooks = 0 if label == "cancelled" else 1
            check(label + ".native_hook_count", len(observed) == expected_hooks)
            check(label + ".transport_calls", transport.calls == len(outcomes))
            check(label + ".ack_count", transport.acknowledged == acknowledgements)
            check(label + ".send_flag", ev._has_send_oper is has_send)
            check(label + ".cancel_propagates", cancelled is (label == "cancelled"))
            if observed:
                check(label + ".no_receipt_in_hook",
                      observed[0]["extra_keys"] == []
                      and observed[0]["incoming_message_id"] == "synthetic-incoming")
            report["cases"][label] = {
                "transport_calls": transport.calls,
                "synthetic_platform_acks": transport.acknowledged,
                "after_sent": list(observed), "cancelled": cancelled,
            }

        transport = Transport([{"message_id": 100003}])
        ev = event(transport)
        returned = await ev.send(MessageEventResult(chain=[Plain(text="Synthetic response.")]))
        check("adapter_discards_platform_ack", returned is None and transport.acknowledged == 1)
        check("adapter_does_not_expose_outgoing_id",
              ev.message_obj.message_id == "synthetic-incoming" and not ev.get_extra())
        report["adapter_return"] = None
    finally:
        star_handlers_registry.remove(handler)
        star_map.pop(module)
        await asyncio.sleep(0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host-source", type=Path, required=True)
    parser.add_argument("--sandbox-parent", type=Path, required=True)
    parser.add_argument("--child", action="store_true")
    args = parser.parse_args()
    host = args.host_source.resolve()
    verify_host(host)
    if not args.child:
        root = Path(tempfile.mkdtemp(prefix="final-c30-contract-", dir=args.sandbox_parent.resolve()))
        for part in ("home", "tmp"):
            (root / part).mkdir()
        env = {
            "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin",
            "HOME": str(root / "home"), "TMPDIR": str(root / "tmp"),
            "ASTRBOT_ROOT": str(root), "ASTRBOT_DISABLE_METRICS": "1",
            "PYTHONDONTWRITEBYTECODE": "1", "LANG": "en_US.UTF-8", "TZ": "UTC",
        }
        with (root / "runtime.log").open("w") as log:
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--host-source", str(host),
                 "--sandbox-parent", str(args.sandbox_parent.resolve()), "--child"],
                cwd=root, env=env, stdout=log, stderr=log, timeout=60, check=False)
        print(json.dumps({"run_id": root.name, "exit_code": result.returncode}))
        if (root / "report.json").exists():
            report = json.loads((root / "report.json").read_text())
            print(json.dumps({"counts": report["counts"], "cases": report["cases"],
                              "fatal_type": report.get("fatal_type")}, indent=2))
        return result.returncode

    sys.dont_write_bytecode = True
    sys.path.insert(0, str(host))
    blocked = []
    guard_network(blocked)
    report = {
        "checks": [], "cases": {}, "host_head": HEAD,
        "source_hashes": {p: hashlib.sha256((host / p).read_bytes()).hexdigest() for p in HOST_FILES},
        "test_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "loaded_product_instances": [], "real_model_calls": 0, "real_platform_calls": 0,
        "product_acceptance": False, "synthetic_listener": True,
    }
    try:
        asyncio.run(probe(report))
    except Exception as exc:
        report["fatal_type"] = type(exc).__name__
        traceback.print_exc()
    report["blocked_runtime_operations"] = dict(Counter(blocked))
    report["counts"] = dict(Counter("passed" if c["passed"] else "failed" for c in report["checks"]))
    report["success"] = not report.get("fatal_type") and not report["counts"].get("failed")
    Path(os.environ["ASTRBOT_ROOT"], "report.json").write_text(json.dumps(report, indent=2))
    return 0 if report["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
