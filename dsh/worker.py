"""DSH-only persistence and JSON-lines boundary; no AstrBot or model imports."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("le_core", ROOT / "__init__.py",
                                            submodule_search_locations=[str(ROOT)])
core = importlib.util.module_from_spec(spec)
sys.modules["le_core"] = core
spec.loader.exec_module(core)
from le_core.contracts import BotAffect, Context, Event, EvidenceRef, Relationship, to_dict
from le_core.domain.emotion import apply_emotion, expression_context, serialize_expression
from le_core.domain.relationship import apply_relationship, initial_relationship


class StateStore:
    def __init__(self, directory):
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(root / "dsh-livingemotion-v1.sqlite3")
        os.chmod(root / "dsh-livingemotion-v1.sqlite3", 0o600)
        self.db.execute("CREATE TABLE IF NOT EXISTS states (key TEXT PRIMARY KEY, body TEXT NOT NULL)")

    def read(self, key):
        row = self.db.execute("SELECT body FROM states WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else {}

    def write(self, key, value):
        self.db.execute("INSERT OR REPLACE INTO states VALUES (?,?)",
                        (key, json.dumps(value, ensure_ascii=False)))

    def delivery(self, args):
        key = "delivery:" + args["deliveryId"]
        previous = self.read(key)
        if previous:
            if previous["fingerprint"] != args["fingerprint"]:
                raise ValueError("delivery_id_conflict")
            return {"reserved": False, "status": previous["status"]}
        with self.db:
            self.write(key, {"fingerprint": args["fingerprint"], "status": "unknown"})
        return {"reserved": True}

    def delivered(self, args):
        key = "delivery:" + args["deliveryId"]
        saved = self.read(key)
        if not saved:
            raise ValueError("unreserved_delivery")
        saved["status"] = args["status"]
        with self.db:
            self.write(key, saved)
        return {"status": saved["status"]}

    def process(self, args):
        context = Context.from_dict(args["context"])
        now = float(args["now"])
        saved = self.read(context.scope_key)
        affect_data = saved.get("affect", {})
        affect_data["evidence"] = tuple(
            EvidenceRef(**{**item, "context": Context.from_dict(item["context"])})
            for item in affect_data.get("evidence", []))
        affect = BotAffect(**affect_data)
        relationship_data = self.read(context.account_key) if args.get("native") else {}
        relationship = Relationship(**relationship_data["relationship"]) \
            if "relationship" in relationship_data else initial_relationship()
        applied = False
        if args.get("event"):
            event = Event.from_dict({**args["event"], "context": args["context"]})
            result = apply_emotion(affect, event, now=now, runtime=saved.get("runtime"))
            affect = result["affect"]
            applied = result["applied"]
            with self.db:
                self.write(context.scope_key, {"affect": to_dict(affect),
                                               "runtime": result["runtime"]})
                if args.get("native"):
                    relation = apply_relationship(relationship, event, now=now,
                                                  runtime=relationship_data.get("runtime"))
                    relationship = relation["relationship"]
                    self.write(context.account_key, {"relationship": to_dict(relationship),
                                                       "runtime": relation["runtime"]})
        prompt = expression_context(affect, None, now=now)
        if args.get("native"):
            prompt["relationship"] = to_dict(relationship)
        return {"affect": to_dict(affect), "applied": applied,
                "relationship": to_dict(relationship) if args.get("native") else None,
                "prompt": serialize_expression(prompt)}


async def serve():
    store = StateStore(sys.argv[1])
    try:
        while line := await asyncio.to_thread(sys.stdin.readline):
            message = json.loads(line)
            if "id" not in message:
                continue
            try:
                operation = {"state": store.process, "reserve": store.delivery, "delivered": store.delivered}
                result = operation[message["op"]](message["args"]) \
                    if message["op"] in operation else {"ready": True}
                response = {"id": message["id"], "result": result}
            except Exception:
                response = {"id": message["id"], "error": "invalid_state_request"}
            print(json.dumps(response, ensure_ascii=False), flush=True)
    finally:
        store.db.close()


if __name__ == "__main__":
    asyncio.run(serve())
