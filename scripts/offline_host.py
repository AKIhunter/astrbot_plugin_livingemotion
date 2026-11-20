"""Minimal host API for offline tools/tests only; never imported by runtime code."""

import sys
from types import ModuleType
import traceback


class RecordedLogger:
    """Record the API calls without constructing a second logging backend."""

    def __init__(self):
        self.messages = []

    @property
    def text(self):
        return "\n".join(self.messages)

    def clear(self):
        self.messages.clear()

    def log(self, level, message, *args, exc_info=False, **kwargs):
        text = str(message) % args if args else str(message)
        if exc_info:
            text += "\n" + traceback.format_exc()
        self.messages.append(text)

    def debug(self, message, *args, **kwargs):
        self.log("debug", message, *args, **kwargs)

    def info(self, message, *args, **kwargs):
        self.log("info", message, *args, **kwargs)

    def warning(self, message, *args, **kwargs):
        self.log("warning", message, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        self.log("error", message, *args, **kwargs)

    def exception(self, message, *args, **kwargs):
        kwargs.setdefault("exc_info", True)
        self.error(message, *args, **kwargs)


def install_offline_api():
    """Supply the missing API in a tool process; preserve an already loaded host."""
    if "astrbot.api" in sys.modules:
        return sys.modules["astrbot.api"]
    if "astrbot" not in sys.modules:
        host = ModuleType("astrbot")
        host.__path__ = []
        host.__livingemotion_offline__ = True
        sys.modules["astrbot"] = host
    api = ModuleType("astrbot.api")
    api.__path__ = []
    api.__livingemotion_offline__ = True
    api.logger = RecordedLogger()
    sys.modules["astrbot.api"] = api
    return api


def remove_offline_api():
    """Explicit native runners discard only the minimal modules created above."""
    for name in ("astrbot.api", "astrbot"):
        module = sys.modules.get(name)
        if getattr(module, "__livingemotion_offline__", False):
            sys.modules.pop(name)
