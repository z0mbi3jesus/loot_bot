"""Repository selection for the loot bot.

The app should continue using Google Sheets by default, but this factory makes
switching to PostgreSQL or another database a configuration change instead of a
code rewrite.
"""

from __future__ import annotations

import os

from sheets import SheetsClient
from postgres_storage import PostgresRepository


def create_repository():
    backend = os.environ.get("DATA_BACKEND", "google_sheets").strip().lower()
    if backend == "postgres":
        return PostgresRepository()
    return SheetsClient()
