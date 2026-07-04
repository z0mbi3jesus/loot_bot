"""Deprecated SQLite implementation of the loot bot repository.

This backend is kept only for reference. The application uses PostgreSQL for
production storage and does not require this module.
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
_COIN_SESSION_HEADERS = [
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

            CREATE TABLE IF NOT EXISTS coin_sessions (
                session_id TEXT PRIMARY KEY,
                start_time TEXT NOT NULL,
                end_time TEXT,
                voice_channel TEXT NOT NULL,
                attendees TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS shaftcoin_balances (
                discord_id INTEGER PRIMARY KEY,
                display_name TEXT NOT NULL,
                balance INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS shaftcoin_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                amount INTEGER NOT NULL,
                balance_after INTEGER NOT NULL,
                reference_id TEXT,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS purchase_requests (
                request_id TEXT PRIMARY KEY,
                requester_id INTEGER NOT NULL,
                requester_name TEXT NOT NULL,
                amount INTEGER NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                approver_id INTEGER,
                approver_name TEXT,
                reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
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

    def start_coin_session(self, voice_channel: str, attendee_ids: list[int]) -> str:
        session_id = str(uuid.uuid4())[:8].upper()
        attendees_str = ",".join(str(i) for i in attendee_ids)
        self._connection.execute(
            """
            INSERT INTO coin_sessions (session_id, start_time, end_time, voice_channel, attendees)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, _now(), None, voice_channel, attendees_str),
        )
        self._connection.commit()
        return session_id

    def end_coin_session(self, session_id: str) -> bool:
        cursor = self._connection.execute(
            "UPDATE coin_sessions SET end_time = ? WHERE session_id = ?",
            (_now(), session_id),
        )
        self._connection.commit()
        return cursor.rowcount > 0

    def get_coin_session(self, session_id: str) -> Optional[dict]:
        row = self._connection.execute(
            """
            SELECT session_id, start_time, end_time, voice_channel, attendees
            FROM coin_sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def get_coin_session_attendees(self, session_id: str) -> list[int]:
        session = self.get_coin_session(session_id)
        if session is None:
            return []
        attendees = session.get("attendees", "")
        if not attendees:
            return []
        return [int(value) for value in attendees.split(",") if value]

    def get_shaftcoin_balance(self, discord_id: int) -> int:
        row = self._connection.execute(
            "SELECT balance FROM shaftcoin_balances WHERE discord_id = ?",
            (discord_id,),
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def adjust_shaftcoin_balance(
        self,
        discord_id: int,
        display_name: str,
        amount: int,
        transaction_type: str,
        description: str,
        reference_id: str | None = None,
    ) -> int:
        current = self.get_shaftcoin_balance(discord_id)
        new_balance = current + amount
        self._connection.execute(
            "INSERT INTO shaftcoin_balances (discord_id, display_name, balance, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(discord_id) DO UPDATE SET display_name = excluded.display_name, balance = excluded.balance, updated_at = excluded.updated_at",
            (discord_id, display_name, new_balance, _now()),
        )
        self._connection.execute(
            "INSERT INTO shaftcoin_transactions (discord_id, type, amount, balance_after, reference_id, description, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (discord_id, transaction_type, amount, new_balance, reference_id, description, _now()),
        )
        self._connection.commit()
        return new_balance

    def create_purchase_request(
        self,
        requester_id: int,
        requester_name: str,
        amount: int,
        description: str,
    ) -> str:
        request_id = str(uuid.uuid4())[:8].upper()
        self._connection.execute(
            """
            INSERT INTO purchase_requests (
                request_id,
                requester_id,
                requester_name,
                amount,
                description,
                status,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (request_id, requester_id, requester_name, amount, description, _now(), _now()),
        )
        self._connection.commit()
        return request_id

    def get_purchase_request(self, request_id: str) -> Optional[dict]:
        row = self._connection.execute(
            """
            SELECT request_id, requester_id, requester_name, amount, description,
                   status, approver_id, approver_name, reason, created_at, updated_at
            FROM purchase_requests
            WHERE request_id = ?
            """,
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def get_purchase_requests(self, status: str | None = None) -> list[dict]:
        if status is None:
            rows = self._connection.execute(
                """
                SELECT request_id, requester_id, requester_name, amount, description,
                       status, approver_id, approver_name, reason, created_at, updated_at
                FROM purchase_requests
                ORDER BY created_at ASC
                """
            ).fetchall()
        else:
            rows = self._connection.execute(
                """
                SELECT request_id, requester_id, requester_name, amount, description,
                       status, approver_id, approver_name, reason, created_at, updated_at
                FROM purchase_requests
                WHERE status = ?
                ORDER BY created_at ASC
                """,
                (status,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_purchase_request_status(
        self,
        request_id: str,
        status: str,
        approver_id: int | None = None,
        approver_name: str | None = None,
        reason: str | None = None,
    ) -> bool:
        cursor = self._connection.execute(
            """
            UPDATE purchase_requests
            SET status = ?, approver_id = ?, approver_name = ?, reason = ?, updated_at = ?
            WHERE request_id = ?
            """,
            (status, approver_id, approver_name, reason or "", _now(), request_id),
        )
        self._connection.commit()
        return cursor.rowcount > 0

    def log_loot(
        self,
        session_id: str,
        item_name: str,
        winner_id: int,
        winner_name: int,
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
