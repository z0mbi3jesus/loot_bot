"""PostgreSQL implementation of the loot bot repository."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import psycopg
from psycopg.rows import dict_row

import config


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


class PostgresRepository:
    def __init__(self) -> None:
        self._connection = psycopg.connect(self._build_dsn(), autocommit=True)
        self._initialize_schema()

    def close(self) -> None:
        self._connection.close()

    def _build_dsn(self) -> str:
        if config.DATABASE_URL:
            return config.DATABASE_URL

        if not config.PGHOST or not config.PGDATABASE or not config.PGUSER or config.PGPASSWORD is None:
            raise RuntimeError(
                "PostgreSQL connection settings are incomplete. Set DATABASE_URL or PGHOST, PGPORT, PGDATABASE, PGUSER, and PGPASSWORD."
            )

        return (
            f"host={config.PGHOST} port={config.PGPORT} dbname={config.PGDATABASE} "
            f"user={config.PGUSER} password={config.PGPASSWORD}"
        )

    def _initialize_schema(self) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS session_tickets (
                    session_id TEXT NOT NULL,
                    discord_id BIGINT NOT NULL,
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
                    discord_id BIGINT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    balance INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS shaftcoin_transactions (
                    id BIGSERIAL PRIMARY KEY,
                    discord_id BIGINT NOT NULL,
                    type TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    balance_after INTEGER NOT NULL,
                    reference_id TEXT,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS purchase_requests (
                    request_id TEXT PRIMARY KEY,
                    requester_id BIGINT NOT NULL,
                    requester_name TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    approver_id BIGINT,
                    approver_name TEXT,
                    reason TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS loot_log (
                    id BIGSERIAL PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    winner_id BIGINT NOT NULL,
                    winner_name TEXT NOT NULL,
                    winner_tickets INTEGER NOT NULL
                );
                """
            )

    def get_session_tickets(self, session_id: str, discord_id: int) -> Optional[dict]:
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT session_id, discord_id, name, tickets
                FROM session_tickets
                WHERE session_id = %s AND discord_id = %s
                """,
                (session_id, discord_id),
            )
            return cursor.fetchone()

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
            with self._connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO session_tickets (session_id, discord_id, name, tickets)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (session_id, discord_id, name, new_tickets),
                )
            return new_tickets

        new_tickets = max(0, int(current["tickets"]) + tickets_delta)
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE session_tickets
                SET name = %s, tickets = %s
                WHERE session_id = %s AND discord_id = %s
                """,
                (name, new_tickets, session_id, discord_id),
            )
        return new_tickets

    def get_session_ticket_standings(self, session_id: str, top_n: int = 15) -> list[dict]:
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT session_id, discord_id, name, tickets
                FROM session_tickets
                WHERE session_id = %s
                ORDER BY tickets DESC, name ASC
                LIMIT %s
                """,
                (session_id, top_n),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_session_ticket_records(self, session_id: str) -> list[dict]:
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT session_id, discord_id, name, tickets
                FROM session_tickets
                WHERE session_id = %s
                ORDER BY tickets DESC, name ASC
                """,
                (session_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_session_attendees(self, session_id: str) -> list[int]:
        session = self.get_session(session_id)
        if session is None:
            return []
        attendees = session.get("attendees", "")
        return [int(value) for value in attendees.split(",") if value]

    def start_session(self, voice_channel: str, attendee_ids: list[int]) -> str:
        session_id = str(uuid.uuid4())[:8].upper()
        attendees_str = ",".join(str(i) for i in attendee_ids)
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sessions (session_id, start_time, end_time, voice_channel, attendees)
                VALUES (%s, %s, NULL, %s, %s)
                """,
                (session_id, _now(), voice_channel, attendees_str),
            )
        return session_id

    def end_session(self, session_id: str) -> bool:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "UPDATE sessions SET end_time = %s WHERE session_id = %s",
                (_now(), session_id),
            )
            return cursor.rowcount > 0

    def get_session(self, session_id: str) -> Optional[dict]:
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT session_id, start_time, end_time, voice_channel, attendees
                FROM sessions
                WHERE session_id = %s
                """,
                (session_id,),
            )
            return cursor.fetchone()

    def start_coin_session(self, voice_channel: str, attendee_ids: list[int]) -> str:
        session_id = str(uuid.uuid4())[:8].upper()
        attendees_str = ",".join(str(i) for i in attendee_ids)
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO coin_sessions (session_id, start_time, end_time, voice_channel, attendees)
                VALUES (%s, %s, NULL, %s, %s)
                """,
                (session_id, _now(), voice_channel, attendees_str),
            )
        return session_id

    def end_coin_session(self, session_id: str) -> bool:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "UPDATE coin_sessions SET end_time = %s WHERE session_id = %s",
                (_now(), session_id),
            )
            return cursor.rowcount > 0

    def get_coin_session(self, session_id: str) -> Optional[dict]:
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT session_id, start_time, end_time, voice_channel, attendees
                FROM coin_sessions
                WHERE session_id = %s
                """,
                (session_id,),
            )
            return cursor.fetchone()

    def get_coin_session_attendees(self, session_id: str) -> list[int]:
        session = self.get_coin_session(session_id)
        if session is None:
            return []
        attendees = session.get("attendees", "")
        return [int(value) for value in attendees.split(",") if value]

    def get_shaftcoin_balance(self, discord_id: int) -> int:
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                "SELECT balance FROM shaftcoin_balances WHERE discord_id = %s",
                (discord_id,),
            )
            row = cursor.fetchone()
            return int(row["balance"]) if row is not None else 0

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
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO shaftcoin_balances (discord_id, display_name, balance, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (discord_id) DO UPDATE
                SET display_name = EXCLUDED.display_name,
                    balance = EXCLUDED.balance,
                    updated_at = EXCLUDED.updated_at
                """,
                (discord_id, display_name, new_balance, _now()),
            )
            cursor.execute(
                """
                INSERT INTO shaftcoin_transactions (
                    discord_id, type, amount, balance_after, reference_id, description, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (discord_id, transaction_type, amount, new_balance, reference_id, description, _now()),
            )
        return new_balance

    def create_purchase_request(
        self,
        requester_id: int,
        requester_name: str,
        amount: int,
        description: str,
    ) -> str:
        request_id = str(uuid.uuid4())[:8].upper()
        with self._connection.cursor() as cursor:
            cursor.execute(
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
                ) VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s)
                """,
                (request_id, requester_id, requester_name, amount, description, _now(), _now()),
            )
        return request_id

    def get_purchase_request(self, request_id: str) -> Optional[dict]:
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT request_id, requester_id, requester_name, amount, description,
                       status, approver_id, approver_name, reason, created_at, updated_at
                FROM purchase_requests
                WHERE request_id = %s
                """,
                (request_id,),
            )
            return cursor.fetchone()

    def get_purchase_requests(self, status: str | None = None) -> list[dict]:
        with self._connection.cursor(row_factory=dict_row) as cursor:
            if status is None:
                cursor.execute(
                    """
                    SELECT request_id, requester_id, requester_name, amount, description,
                           status, approver_id, approver_name, reason, created_at, updated_at
                    FROM purchase_requests
                    ORDER BY created_at ASC
                    """
                )
            else:
                cursor.execute(
                    """
                    SELECT request_id, requester_id, requester_name, amount, description,
                           status, approver_id, approver_name, reason, created_at, updated_at
                    FROM purchase_requests
                    WHERE status = %s
                    ORDER BY created_at ASC
                    """,
                    (status,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def update_purchase_request_status(
        self,
        request_id: str,
        status: str,
        approver_id: int | None = None,
        approver_name: str | None = None,
        reason: str | None = None,
    ) -> bool:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE purchase_requests
                SET status = %s,
                    approver_id = %s,
                    approver_name = %s,
                    reason = %s,
                    updated_at = %s
                WHERE request_id = %s
                """,
                (status, approver_id, approver_name, reason or "", _now(), request_id),
            )
            return cursor.rowcount > 0

    def log_loot(
        self,
        session_id: str,
        item_name: str,
        winner_id: int,
        winner_name: str,
        winner_tickets: int,
    ) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO loot_log (timestamp, session_id, item_name, winner_id, winner_name, winner_tickets)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (_now(), session_id, item_name, winner_id, winner_name, winner_tickets),
            )
