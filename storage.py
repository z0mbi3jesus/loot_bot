"""Storage abstraction for the loot bot.

The application should only depend on this repository interface. That makes it
straightforward to keep Google Sheets for now while preparing a later migration
to PostgreSQL or another production database.
"""

from __future__ import annotations

from typing import Protocol


class LootRepository(Protocol):
    def get_session_tickets(self, session_id: str, discord_id: int) -> dict | None:
        ...

    def upsert_session_member(
        self,
        session_id: str,
        discord_id: int,
        name: str,
        tickets_delta: int = 0,
    ) -> int:
        ...

    def get_session_ticket_standings(self, session_id: str, top_n: int = 15) -> list[dict]:
        ...

    def get_session_ticket_records(self, session_id: str) -> list[dict]:
        ...

    def get_session_attendees(self, session_id: str) -> list[int]:
        ...

    def start_coin_session(self, voice_channel: str, attendee_ids: list[int]) -> str:
        ...

    def end_coin_session(self, session_id: str) -> bool:
        ...

    def get_coin_session(self, session_id: str) -> dict | None:
        ...

    def get_coin_session_attendees(self, session_id: str) -> list[int]:
        ...

    def get_shaftcoin_balance(self, discord_id: int) -> int:
        ...

    def adjust_shaftcoin_balance(
        self,
        discord_id: int,
        display_name: str,
        amount: int,
        transaction_type: str,
        description: str,
        reference_id: str | None = None,
    ) -> int:
        ...

    def create_purchase_request(
        self,
        requester_id: int,
        requester_name: str,
        amount: int,
        description: str,
    ) -> str:
        ...

    def get_purchase_request(self, request_id: str) -> dict | None:
        ...

    def get_purchase_requests(self, status: str | None = None) -> list[dict]:
        ...

    def update_purchase_request_status(
        self,
        request_id: str,
        status: str,
        approver_id: int | None = None,
        approver_name: str | None = None,
        reason: str | None = None,
    ) -> bool:
        ...

    def start_session(self, voice_channel: str, attendee_ids: list[int]) -> str:
        ...

    def end_session(self, session_id: str) -> bool:
        ...

    def get_session(self, session_id: str) -> dict | None:
        ...

    def log_loot(
        self,
        session_id: str,
        item_name: str,
        winner_id: int,
        winner_name: str,
        winner_tickets: int,
    ) -> None:
        ...
