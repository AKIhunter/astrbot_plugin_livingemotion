"""Account evidence compression preserves state and old persisted snapshots."""
from astrbot_plugin_livingemotion.runtime.projector import (
    account_affect, account_affect_token, encode_account_runtime, encode_account_state,
)
from astrbot_plugin_livingemotion.contracts import BotAffect, EvidenceRef, StateRecord, to_dict


def test_legacy_and_compressed_account_state_have_identical_evidence(le_context):
    evidence = EvidenceRef("livingemotion", "synthetic", le_context,
                           le_context.account_id, le_context.bot_id, "interaction",
                           100, 200, source_ids=("synthetic",))
    state = BotAffect(evidence=(evidence,))
    payload = to_dict(state)
    runtime = {"version": 1, "scope_key": le_context.scope_key, "seen": [], "stimuli": []}
    results = []
    for encoded in (payload, encode_account_state(payload)):
        record = StateRecord("relationship", {"_account_affect": {
            "context": account_affect_token(le_context), "state": encoded,
            "runtime": encode_account_runtime(runtime)}}, 1, 0, 100, le_context.account_id)
        result = account_affect(record, le_context)
        assert result is not None
        results.append(result)
    assert results[0] == results[1] == (state, runtime)
    assert payload["evidence"] == to_dict(state)["evidence"]
