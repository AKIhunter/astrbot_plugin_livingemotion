"""Explicit host inputs for the offline Provider lane, never a workspace fallback."""

from importlib.metadata import PackageNotFoundError, version
import os
from pathlib import Path
import sys
import tomllib


def packages(names):
    result = {}
    for name in names:
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = None
    return result


def configure_host(source=None):
    source = source or os.environ.get("ASTRBOT_HOST_SOURCE")
    if not source:
        raise RuntimeError("host_source_required")
    root = Path(source).expanduser().resolve()
    provider = root / "astrbot/core/provider/sources/openai_source.py"
    if not provider.is_file() or not (root / "pyproject.toml").is_file():
        raise RuntimeError("invalid_host_source")
    with (root / "pyproject.toml").open("rb") as stream:
        host_version = tomllib.load(stream)["project"]["version"]
    if any(value is None for value in packages(("openai", "httpx")).values()):
        raise RuntimeError("host_sdk_dependencies_missing")
    loaded = sys.modules.get("astrbot")
    if loaded is not None and not Path(loaded.__file__).resolve().is_relative_to(root):
        raise RuntimeError("different_host_already_imported")
    sys.path.insert(0, str(root))
    return root, host_version
