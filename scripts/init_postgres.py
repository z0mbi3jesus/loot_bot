"""Create the PostgreSQL database schema for loot_bot."""

from postgres_storage import PostgresRepository


def main() -> None:
    repo = PostgresRepository()
    repo.close()
    print(
        "Initialized PostgreSQL schema for loot_bot: session_tickets, sessions, coin_sessions, shaftcoin_balances, shaftcoin_transactions, purchase_requests, loot_log"
    )


if __name__ == "__main__":
    main()
