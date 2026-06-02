"""
Google Sheets integration layer.

Spreadsheet layout (all created automatically on first run):
  Sheet "tickets"   — discord_id | name | tickets
  Sheet "sessions"  — session_id | start_time | end_time | voice_channel | attendees
  Sheet "loot_log"  — timestamp | session_id | item_name | winner_id | winner_name | tickets_spent
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

_TICKET_HEADERS = ["discord_id", "name", "tickets"]
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
    "tickets_spent",
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


class SheetsClient:
    """Thin wrapper around gspread for the loot-bot data model."""

    def __init__(self) -> None:
        gc = gspread.service_account(filename=config.GSPREAD_SERVICE_ACCOUNT_FILE)
        self._sheet: Spreadsheet = gc.open_by_key(config.SPREADSHEET_ID)
        self._tickets: Worksheet = self._ensure_sheet("tickets", _TICKET_HEADERS)
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

    def _find_ticket_row(self, discord_id: int) -> Optional[int]:
        """Return 1-based row index for a member, or None if not found."""
        col = self._tickets.col_values(1)  # discord_id column
        try:
            return col.index(str(discord_id)) + 1
        except ValueError:
            return None

    def _find_session_row(self, session_id: str) -> Optional[int]:
        col = self._sessions.col_values(1)
        try:
            return col.index(session_id) + 1
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Ticket operations
    # ------------------------------------------------------------------

    def get_tickets(self, discord_id: int) -> Optional[dict]:
        """Return {discord_id, name, tickets} or None."""
        row = self._find_ticket_row(discord_id)
        if row is None:
            return None
        values = self._tickets.row_values(row)
        return {"discord_id": values[0], "name": values[1], "tickets": int(values[2])}

    def upsert_member(self, discord_id: int, name: str, tickets_delta: int = 0) -> int:
        """
        Add member if new, then apply tickets_delta.
        Returns the new ticket total.
        """
        row = self._find_ticket_row(discord_id)
        if row is None:
            new_tickets = max(0, tickets_delta)
            self._tickets.append_row(
                [str(discord_id), name, new_tickets], value_input_option="RAW"
            )
            return new_tickets

        current = int(self._tickets.cell(row, 3).value or 0)
        # Update name in case display name changed
        self._tickets.update_cell(row, 2, name)
        new_tickets = max(0, current + tickets_delta)
        self._tickets.update_cell(row, 3, new_tickets)
        return new_tickets

    def get_standings(self, top_n: int = 15) -> list[dict]:
        """Return top_n members sorted by ticket count descending."""
        records = self._tickets.get_all_records()
        sorted_records = sorted(records, key=lambda r: int(r.get("tickets", 0)), reverse=True)
        return sorted_records[:top_n]

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
        tickets_spent: int,
    ) -> None:
        self._loot.append_row(
            [
                _now(),
                session_id,
                item_name,
                str(winner_id),
                winner_name,
                str(tickets_spent),
            ],
            value_input_option="RAW",
        )
