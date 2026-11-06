"""Authenticated management entry point, separate from the in-process public API."""

from .protocols import ConsoleApplication
from .routes import PageAPI

__all__ = ["ConsoleApplication", "PageAPI"]
