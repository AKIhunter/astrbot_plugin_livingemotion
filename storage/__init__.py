"""Owned SQLite persistence, never a facade for another plugin's database."""

from .sqlite import SQLiteStore, StoreClosed

__all__ = ["SQLiteStore", "StoreClosed"]
