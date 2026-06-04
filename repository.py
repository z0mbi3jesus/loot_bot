"""Repository selection for the loot bot.

The app should continue using Google Sheets by default, but this factory makes
switching to SQLite or another database a configuration change instead of a
code rewrite.
"""

from __future__ import annotations

import os

from sheets import SheetsClient
from sqlite_storage import SQLiteRepository


def create_repository():
    backend = os.environ.get("DATA_BACKEND", "google_sheets").strip().lower()
    if backend == "sqlite":
        database_path = os.environ.get("SQLITE_DATABASE_PATH", "loot_bot.sqlite3")
        return SQLiteRepository(database_path=database_path)
    return SheetsClient()
