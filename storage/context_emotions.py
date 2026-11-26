"""人级对象情绪：用户维度下同一 QQ 的委屈/受伤/害羞在群与私聊间共用一行。

复用 owner_states（owner_key=人级键，kind=context_emotion），不新增表，
回滚旧版本代码时不会触发 schema_newer_than_code。
"""

import json

from ..contracts import StateRecord, account_person_key

PERSON_KIND = "context_emotion"


def person_dimension(config) -> bool:
    return getattr(config, "context_emotions_dimension", "conversation") == "user"


def person_value(context, state, fingerprint, epoch) -> dict:
    return {"version": 1, "target": context.account_id, "persona": fingerprint,
            "epoch": epoch, "context_emotions": state}


class ContextEmotionStore:
    def _person_record(self, db, context):
        row = db.execute(
            "SELECT version,updated_at,value_json FROM owner_states WHERE owner_key=? AND kind=?",
            (account_person_key(context), PERSON_KIND),
        ).fetchone()
        if row is None:
            return None
        return StateRecord(PERSON_KIND, json.loads(row["value_json"]), row["version"],
                           self._generation(db, context), row["updated_at"], context.account_id)

    async def context_emotion_record(self, context, scene_record=None):
        """对象情绪所在的记录：用户维度读人级记录，会话维度沿用会话关系记录。"""
        if person_dimension(self.config) and context.account_id:
            return await self._run(lambda db: self._person_record(db, context))
        if scene_record is None and context.account_id:
            return await self.get_state(context, "relationship", context.account_id)
        return scene_record

    def _with_person_record(self, db, context, snapshot):
        """用户维度下投影快照一并读出人级记录，计算与读取同一份 SQL 快照。"""
        generation, records = snapshot
        if person_dimension(self.config) and context.account_id:
            records["context_emotion"] = self._person_record(db, context)
        return generation, records

    def _write_person(self, db, context, write, now, encoded=None):
        from .sqlite import _Rejected, _state_json
        if not context.account_id or write.record_key != context.account_id:
            raise ValueError("context emotion requires source account record_key")
        if type(write.expected_version) is not int or write.expected_version < 0:
            raise ValueError("invalid expected_version")
        key = account_person_key(context)
        row = db.execute("SELECT version FROM owner_states WHERE owner_key=? AND kind=?",
                         (key, PERSON_KIND)).fetchone()
        if (row[0] if row else 0) != write.expected_version:
            raise _Rejected("version_conflict")
        payload = encoded[id(write.value)] if encoded is not None else _state_json(write.value)
        if len(payload) > 65536:
            raise ValueError("state payload too large")
        db.execute(
            """INSERT INTO owner_states VALUES(?,?,?,?,?)
               ON CONFLICT(owner_key,kind) DO UPDATE SET version=excluded.version,
               updated_at=excluded.updated_at,value_json=excluded.value_json""",
            (key, PERSON_KIND, write.expected_version + 1, now, payload),
        )
        return {f"{PERSON_KIND}": write.expected_version + 1}
