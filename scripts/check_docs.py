"""Generate the field reference from schema and real Console; validate all docs."""
from __future__ import annotations

import argparse
import ast
import dataclasses
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from urllib.parse import unquote, urlsplit
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
from astrbot_plugin_livingemotion.config import Config, LEGACY_FIELDS
from astrbot_plugin_livingemotion.runtime.console import Console, SETTINGS_GROUPS
from astrbot_plugin_livingemotion.runtime.config_help import field_help


def cell(value):
    return str(value).replace("|", "&#124;").replace("\n", "<br>")


def anchors(text):
    seen, result = Counter(), set()
    for heading in re.findall(r"(?m)^#{1,6} +(.+?) *#* *$", text):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        result.add(slug + (f"-{seen[slug]}" if seen[slug] else ""))
        seen[slug] += 1
    result.update(re.findall(r'(?:id|name)=["\']([^"\']+)["\']', text))
    return result


def public_fields():
    obj = SimpleNamespace(config=Config(), config_revision="documentation",
                          _settings_groups=Console._settings_groups)
    return Console.config_dto(obj)["fields"]


def bounds():
    """Read explicit numeric maxima/ranges, rather than assuming every slider is enforced."""
    result = {}
    tree = ast.parse((ROOT / "config.py").read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.For) or not isinstance(node.target, ast.Tuple):
            continue
        names = [getattr(item, "id", "") for item in node.target.elts]
        if names not in (["name", "maximum"], ["name", "low", "high"]):
            continue
        try:
            rows = ast.literal_eval(node.iter)
        except (ValueError, TypeError):
            continue
        for row in rows:
            if len(row) == 2:
                result[row[0]] = (1, row[1])
            elif len(row) == 3:
                result[row[0]] = tuple(row[1:])
    result.update({
        "promise_max_active": (1, 10), "promise_recall_limit": (1, 8),
        "promise_trace_ttl_hours": (1, 168), "weather_weight_scale": (0, 3),
        "diary_retries": (0, 2), "lie_in_min_minutes": (0, 1440),
        "lie_in_max_minutes": (0, 1440), "closing_lead_minutes": (0, 60),
        "emotion_quiet_start_hour": (0, 23), "emotion_quiet_end_hour": (0, 23),
        "energy_reply_cost": (0, 100), "energy_fatigue_per_minute": (0, 100),
        "energy_recovery_per_minute": (0, 100), "energy_comfort_percent": (0, 100),
        "behavior_random_min_minutes": (1, Config().behavior_random_max_minutes),
    })
    return result


def reference():
    schema = json.loads((ROOT / "_conf_schema.json").read_text())
    fields = public_fields()
    assert {f["key"] for f in fields} == set(schema), "Schema/Console field coverage"
    groups, limits = dict(SETTINGS_GROUPS), bounds()
    output = []
    for section, label in SETTINGS_GROUPS:
        selected = [f for f in fields if f["section"] == section]
        if not selected:
            continue
        output += [f"### {label}", "",
                   "| 配置项 / 默认值 | 设置位置与范围 | 作用、开启关闭效果和例子 |",
                   "| --- | --- | --- |"]
        for f in selected:
            key = f["key"]
            help_ = field_help(key)
            assert help_["help"] and help_["example"], f"Missing help: {key}"
            location = "设置 → " + groups[section]
            if f.get("subsection_label"):
                location += " → " + f["subsection_label"]
            limit = limits.get(key)
            if key == "behavior_random_min_minutes":
                range_text = "1至当前最长等待；最长不得超过10080分钟"
            elif limit:
                range_text = f"{limit[0]}–{limit[1]}"
                range_text += "，步进0.1" if schema[key]["type"] == "float" else "，整数"
                if f.get("unit"):
                    range_text += "，" + f["unit"]
            elif schema[key].get("options"):
                range_text = " / ".join(schema[key]["options"])
            elif schema[key]["type"] == "bool":
                range_text = "独立开关"
            elif schema[key]["type"] in ("int", "float"):
                range_text = "正整数" if schema[key]["type"] == "int" else "有限数值"
                if f.get("unit"):
                    range_text += "，" + f["unit"]
            else:
                range_text = "文字 / 标识；具体限制见说明"
            default = json.dumps(schema[key]["default"], ensure_ascii=False)
            details = help_["help"] + " " + help_["details"] + " 例：" + help_["example"]
            output.append(f"| `{key}`<br>`{cell(default)}` | {cell(location)}<br>{cell(range_text)} | {cell(details)} |")
        output.append("")
    return "\n".join(output).rstrip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Regenerate the marked reference only")
    args = parser.parse_args()
    path = ROOT / "docs/config-reference.md"
    content = path.read_text()
    pattern = r"(<!-- fields:start -->\n).*?(<!-- fields:end -->)"
    generated = reference()
    candidate = re.sub(pattern, lambda m: m[1] + generated + "\n" + m[2], content, flags=re.S)
    assert candidate != content or generated in content, "Reference markers missing"
    if args.write:
        path.write_text(candidate)
    else:
        assert content == candidate, "Run python scripts/check_docs.py --write after help/schema changes"
    defaults = dataclasses.asdict(Config())
    schema = json.loads((ROOT / "_conf_schema.json").read_text())
    assert set(defaults) - set(schema) == LEGACY_FIELDS
    for key, f in schema.items():
        actual, expected = defaults[key], f["default"]
        if key == "dream_theme_pool":
            actual, expected = json.loads(actual), json.loads(expected)
        assert actual == expected, key
    links = 0
    docs = [ROOT / n for n in ("README.md", "README.en.md", "CHANGELOG.md", "THIRD_PARTY_NOTICES.md")]
    docs += sorted((ROOT / "docs").rglob("*.md"))
    for doc in docs:
        text = doc.read_text()
        assert not any(line.rstrip() != line for line in text.splitlines()), doc
        text = re.sub(r"(?ms)^```.*?^```[^\n]*$", "", text)
        for target in re.findall(r"!?\[[^\]\n]*\]\(([^)\s]+)\)", text):
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue
            destination = (doc.parent / unquote(parsed.path)).resolve() if parsed.path else doc
            assert destination.is_relative_to(ROOT) and destination.exists(), (doc, target)
            if parsed.fragment and destination.suffix == ".md":
                assert unquote(parsed.fragment) in anchors(destination.read_text()), (doc, target)
            links += 1
    api_text = (ROOT / "docs/api.md").read_text()
    route_tree = ast.parse((ROOT / "page_api/routes.py").read_text())
    routes = next(ast.literal_eval(n.value) for n in route_tree.body
                  if isinstance(n, ast.Assign) and any(
                      isinstance(t, ast.Name) and t.id == "ROUTES" for t in n.targets))
    for route, method in routes:
        assert f"| {method} {route} |" in api_text, ("Missing route documentation", route)
    api_tree = ast.parse((ROOT / "api.py").read_text())
    for cls in (n for n in api_tree.body if isinstance(n, ast.ClassDef)):
        for method in cls.body:
            if isinstance(method, ast.AsyncFunctionDef) and not method.name.startswith("_"):
                assert f"| {method.name} |" in api_text, ("Missing facade documentation", method.name)
    print(f"PASS {len(docs)} docs / {links} local links / {len(schema)} fields / {len(defaults)} defaults")


if __name__ == "__main__":
    main()
