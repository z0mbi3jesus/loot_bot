"""SQLite implementation of the loot bot repository.

This backend is intentionally simple so the app can be moved away from Google
Sheets later without rewriting the command layer again.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_SESSION_TICKET_HEADERS = ["session_id", "discord_id", "name", "tickets"]
_SESSION_HEADERS = [
    "session_id",
    "start_time",
    "end_time",
    "voice_channel",
    "attendees",
]
_LOOT_HEADERS = [
    "timestamp",
    "session_id",
    "item_name",
    "winner_id",
    "winner_name",
    "winner_tickets",
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


class SQLiteRepository:
    def __init__(self, database_path: str = "loot_bot.sqlite3") -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self._path)
        self._connection.row_factory = sqlite3.Row
        self._initialize_schema()

    def close(self) -> None:
        self._connection.close()

    def _initialize_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS session_tickets (
                session_id TEXT NOT NULL,
                discord_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                tickets INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (session_id, discord_id)
            );

            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                start_time TEXT NOT NULL,
                end_time TEXT,
                voice_channel TEXT NOT NULL,
                attendees TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS loot_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                session_id TEXT NOT NULL,
                item_name TEXT NOT NULL,
                winner_id INTEGER NOT NULL,
                winner_name TEXT NOT NULL,
                winner_tickets INTEGER NOT NULL
            );
            """
        )
        self._connection.commit()

    def get_session_tickets(self, session_id: str, discord_id: int) -> Optional[dict]:
        row = self._connection.execute(
            """
            SELECT session_id, discord_id, name, tickets
            FROM session_tickets
            WHERE session_id = ? AND discord_id = ?
            """,
            (session_id, discord_id),
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def upsert_session_member(
        self,
        session_id: str,
        discord_id: int,
        name: str,
        tickets_delta: int = 0,
    ) -> int:
        current = self.get_session_tickets(session_id, discord_id)
        if current is None:
            new_tickets = max(0, tickets_delta)
            self._connection.execute(
                """
                INSERT INTO session_tickets (session_id, discord_id, name, tickets)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, discord_id, name, new_tickets),
            )
            self._connection.commit()
            return new_tickets

        new_tickets = max(0, int(current["tickets"]) + tickets_delta)
        self._connection.execute(
            """
            UPDATE session_tickets
            SET name = ?, tickets = ?
            WHERE session_id = ? AND discord_id = ?
            """,
            (name, new_tickets, session_id, discord_id),
        )
        self._connection.commit()
        return new_tickets

    def get_session_ticket_records(self, session_id: str) -> list[dict]:
        rows = self._connection.execute(
            """
            SELECT session_id, discord_id, name, tickets
            FROM session_tickets
            WHERE session_id = ?
            ORDER BY tickets DESC, name ASC
            """,
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_session_ticket_standings(self, session_id: str, top_n: int = 15) -> list[dict]:
        return self.get_session_ticket_records(session_id)[:top_n]

    def get_session_attendees(self, session_id: str) -> list[int]:
        session = self.get_session(session_id)
        if session is None:
            return []
        attendees = session.get("attendees", "")
        if not attendees:
            return []
        return [int(value) for value in attendees.split(",") if value]

    def start_session(self, voice_channel: str, attendee_ids: list[int]) -> str:
        session_id = str(uuid.uuid4())[:8].upper()
        attendees_str = ",".join(str(i) for i in attendee_ids)
        self._connection.execute(
            """
            INSERT INTO sessions (session_id, start_time, end_time, voice_channel, attendees)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, _now(), None, voice_channel, attendees_str),
        )
        self._connection.commit()
        return session_id

    def end_session(self, session_id: str) -> bool:
        cursor = self._connection.execute(
            "UPDATE sessions SET end_time = ? WHERE session_id = ?",
            (_now(), session_id),
        )
        self._connection.commit()
        return cursor.rowcount > 0

    def get_session(self, session_id: str) -> Optional[dict]:
        row = self._connection.execute(
            """
            SELECT session_id, start_time, end_time, voice_channel, attendees
            FROM sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def log_loot(
        self,
        session_id: str,
        item_name: str,
        winner_id: int,
        winner_name: str,
        winner_tickets: int,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO loot_log (timestamp, session_id, item_name, winner_id, winner_name, winner_tickets)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (_now(), session_id, item_name, winner_id, winner_name, winner_tickets),
        )
        self._connection.commit()
