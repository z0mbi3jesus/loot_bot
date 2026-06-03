"""
Google Sheets integration layer.

Spreadsheet layout (all created automatically on first run):
    Sheet "session_tickets" — session_id | discord_id | name | tickets
    Sheet "sessions"        — session_id | start_time | end_time | voice_channel | attendees
    Sheet "loot_log"        — timestamp | session_id | item_name | winner_id | winner_name | winner_tickets
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import gspread
from gspread import Spreadsheet, Worksheet

import config

# ---------------------------------------------------------------------------
# Column indices (1-based, matching the header order above)
# ---------------------------------------------------------------------------

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


class SheetsClient:
    """Thin wrapper around gspread for the loot-bot data model."""

    def __init__(self) -> None:
        gc = gspread.service_account(filename=config.GSPREAD_SERVICE_ACCOUNT_FILE)
        self._sheet: Spreadsheet = gc.open_by_key(config.SPREADSHEET_ID)
        self._session_tickets: Worksheet = self._ensure_sheet(
            "session_tickets", _SESSION_TICKET_HEADERS
        )
        self._sessions: Worksheet = self._ensure_sheet("sessions", _SESSION_HEADERS)
        self._loot: Worksheet = self._ensure_sheet("loot_log", _LOOT_HEADERS)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_sheet(self, title: str, headers: list[str]) -> Worksheet:
        """Return worksheet, creating it with headers if it doesn't exist."""
        try:
            ws = self._sheet.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = self._sheet.add_worksheet(title=title, rows=1000, cols=len(headers))
            ws.append_row(headers, value_input_option="RAW")
        return ws

    def _find_session_ticket_row(self, session_id: str, discord_id: int) -> Optional[int]:
        """Return 1-based row index for a session/member pair, or None if not found."""
        rows = self._session_tickets.get_all_values()
        for index, values in enumerate(rows[1:], start=2):
            if len(values) >= 2 and values[0] == session_id and values[1] == str(discord_id):
                return index
        return None

    def _find_session_row(self, session_id: str) -> Optional[int]:
        col = self._sessions.col_values(1)
        try:
            return col.index(session_id) + 1
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Session ticket operations
    # ------------------------------------------------------------------

    def get_session_tickets(self, session_id: str, discord_id: int) -> Optional[dict]:
        """Return {session_id, discord_id, name, tickets} or None."""
        row = self._find_session_ticket_row(session_id, discord_id)
        if row is None:
            return None
        values = self._session_tickets.row_values(row)
        return {
            "session_id": values[0],
            "discord_id": values[1],
            "name": values[2],
            "tickets": int(values[3]),
        }

    def upsert_session_member(
        self,
        session_id: str,
        discord_id: int,
        name: str,
        tickets_delta: int = 0,
    ) -> int:
        """
        Add member for a session if new, then apply tickets_delta.
        Returns the new ticket total for that session/member pair.
        """
        row = self._find_session_ticket_row(session_id, discord_id)
        if row is None:
            new_tickets = max(0, tickets_delta)
            self._session_tickets.append_row(
                [session_id, str(discord_id), name, new_tickets], value_input_option="RAW"
            )
            return new_tickets

        current = int(self._session_tickets.cell(row, 4).value or 0)
        # Update name in case display name changed
        self._session_tickets.update_cell(row, 3, name)
        new_tickets = max(0, current + tickets_delta)
        self._session_tickets.update_cell(row, 4, new_tickets)
        return new_tickets

    def get_session_ticket_standings(self, session_id: str, top_n: int = 15) -> list[dict]:
        """Return top_n session rows sorted by ticket count descending."""
        records = [r for r in self._session_tickets.get_all_records() if r.get("session_id") == session_id]
        sorted_records = sorted(records, key=lambda r: int(r.get("tickets", 0)), reverse=True)
        return sorted_records[:top_n]

    def get_session_attendees(self, session_id: str) -> list[int]:
        session = self.get_session(session_id)
        if session is None:
            return []
        attendees = session.get("attendees", "")
        if not attendees:
            return []
        return [int(value) for value in attendees.split(",") if value]

    # ------------------------------------------------------------------
    # Session operations
    # ------------------------------------------------------------------

    def start_session(
        self,
        voice_channel: str,
        attendee_ids: list[int],
    ) -> str:
        """
        Record a new session snapshot.
        Returns the new session_id.
        """
        session_id = str(uuid.uuid4())[:8].upper()
        attendees_str = ",".join(str(i) for i in attendee_ids)
        self._sessions.append_row(
            [
                session_id,
                _now(),
                "",  # end_time — filled by end_session
                voice_channel,
                attendees_str,
            ],
            value_input_option="RAW",
        )
        return session_id

    def end_session(self, session_id: str) -> bool:
        """Stamp end_time on an open session. Returns False if not found."""
        row = self._find_session_row(session_id)
        if row is None:
            return False
        self._sessions.update_cell(row, 3, _now())
        return True

    def get_session(self, session_id: str) -> Optional[dict]:
        row = self._find_session_row(session_id)
        if row is None:
            return None
        values = self._sessions.row_values(row)
        headers = _SESSION_HEADERS
        return dict(zip(headers, values))

    # ------------------------------------------------------------------
    # Loot log
    # ------------------------------------------------------------------

    def log_loot(
        self,
        session_id: str,
        item_name: str,
        winner_id: int,
        winner_name: str,
        winner_tickets: int,
    ) -> None:
        self._loot.append_row(
            [
                _now(),
                session_id,
                item_name,
                str(winner_id),
                winner_name,
                str(winner_tickets),
            ],
            value_input_option="RAW",
        )
