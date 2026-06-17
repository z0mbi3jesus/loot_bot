"""Create the SQLite database and required tables for loot_bot.

Run this on the target machine to create `loot_bot.sqlite3` with the
expected schema. The script uses the same initialization logic as the
app's `SQLiteRepository` so it stays in sync.
"""
from sqlite_storage import SQLiteRepository


def main() -> None:
    repo = SQLiteRepository(database_path="loot_bot.sqlite3")
    repo.close()
    print("Initialized loot_bot.sqlite3 with tables: session_tickets, sessions, loot_log")


if __name__ == "__main__":
    main()
