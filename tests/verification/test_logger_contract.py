"""Keep plugin logs on AstrBot's per-plugin routing and level controls."""

import ast
import importlib
from pathlib import Path

from astrbot.api import logger


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIRS = ("adapters", "domain", "integrations", "page_api", "ports",
                "runtime", "services", "storage")


def test_all_sources_reject_builtin_logging_and_runtime_uses_api_logger():
    sources = list(ROOT.glob("*.py"))
    for directory in (*RUNTIME_DIRS, "scripts", "tests"):
        sources.extend((ROOT / directory).rglob("*.py"))
    for path in sources:
        tree = ast.parse(path.read_text(), filename=str(path))
        runtime = path.parent == ROOT or path.relative_to(ROOT).parts[0] in RUNTIME_DIRS
        imports = []
        uses_logger = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(item.name.split(".")[0] != "logging" for item in node.names), path
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] != "logging", path
                imports.extend((node.module, item.asname or item.name)
                               for item in node.names if item.name == "logger")
                assert all(node.module == "astrbot.api" for item in node.names
                           if item.name == "logger"), path
            if runtime and isinstance(node, ast.Name) and node.id == "logger":
                assert not isinstance(node.ctx, ast.Store), path
                uses_logger = uses_logger or isinstance(node.ctx, ast.Load)
        if runtime and uses_logger:
            assert imports == [("astrbot.api", "logger")], path
            if path.name != "main.py":
                module = importlib.import_module(
                    "astrbot_plugin_livingemotion." +
                    ".".join(path.relative_to(ROOT).with_suffix("").parts))
                assert module.logger is logger, path
