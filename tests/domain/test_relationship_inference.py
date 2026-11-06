from dataclasses import replace

import pytest

from astrbot_plugin_livingemotion.domain.relationship_inference import (
    RelationshipStatement, infer_relationships,
)


def people():
    return [{"id": f"{p}/{a}", "platform": p, "account_id": a, "label": label}
            for p, a, label in (("qq", "123", "小林"), ("qq", "456", "小雨"),
                                ("bilibili", "456", "小雨"), ("qq", "789", "小林"))]


def statement(context, body, at=1000, **changes):
    return RelationshipStatement(replace(context, platform="qq", account_id="123"),
                                 f"source-{at}", "聊天记录", at, body, "123", **changes)


@pytest.mark.parametrize("body,kind", [
    ("我和@456是朋友", "朋友"), ("我与456是同学", "同学"),
    ("@456是我的同事", "同事"), ("qq123和qq456是室友", "室友"),
    ("QQ:123和B站:456是搭档", "搭档"),
    ("[CQ:at,qq=456]是我的家人", "家人"),
    ("我和小雨是好友", "朋友"),
])
def test_explicit_accounts_and_unique_platform_name(le_context, body, kind):
    edges = infer_relationships(people(), [statement(le_context, body)])
    assert len(edges) == 1 and edges[0]["relation"] == kind
    assert edges[0]["inferred"] is True and edges[0]["evidence"][0]["excerpt"] == body
    assert edges[0]["evidence"][0]["basis"] == ("本人陈述" if "我" in body else "他人陈述")
    if "B站" in body:
        assert "bilibili/456" in (edges[0]["source"], edges[0]["target"])
    else:
        assert "qq/456" in (edges[0]["source"], edges[0]["target"])


@pytest.mark.parametrize("body", [
    "我和@456在同一个群", "我和@456", "我和@456是朋友吗",
    "我和@456是不是朋友", "假如我和@456是朋友", "我和@456可能是朋友",
    "小说里我和@456是朋友", "梦里我和@456是朋友", "我和@456不是朋友",
    "我和@999是朋友", "我和小林是朋友", "我和@456以前是朋友",
    "我和@456是朋友？", "我和@456不再是朋友", "我和@456并非朋友",
    "我和@456是同事的朋友", "我和@45678是朋友",
])
def test_uncertain_unknown_ambiguous_and_cooccurrence_do_not_invent(le_context, body):
    assert infer_relationships(people(), [statement(le_context, body)]) == []


@pytest.mark.parametrize("verb", ["不是", "不再是", "并非", "并不是"])
def test_new_denial_cancels_claim_and_later_claim_can_reestablish(le_context, verb):
    old = statement(le_context, "我和@456是朋友", 1000)
    denial = statement(le_context, f"我和@456{verb}朋友", 1001)
    assert infer_relationships(people(), [old, denial]) == []
    new = statement(le_context, "我和@456是朋友", 1002)
    result = infer_relationships(people(), [old, denial, new])
    assert len(result) == 1 and len(result[0]["evidence"]) == 1
    assert infer_relationships(people(), [old, replace(denial, at=1000)]) == []


def test_evidence_deduplicates_and_caps_without_scores(le_context):
    rows = [statement(le_context, "我和@456是朋友", n) for n in range(20)]
    edges = infer_relationships(people(), [*rows, *rows])
    assert len(edges) == 1 and len(edges[0]["evidence"]) == 4
    assert "score" not in edges[0]
    assert infer_relationships(people()[:1], rows) == []
