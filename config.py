import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN: str = os.environ["DISCORD_TOKEN"]
GUILD_ID: int = int(os.environ["GUILD_ID"])

# Google Sheets
GSPREAD_SERVICE_ACCOUNT_FILE: str = os.environ.get(
    "GSPREAD_SERVICE_ACCOUNT_FILE", "service_account.json"
)
SPREADSHEET_ID: str = os.environ["SPREADSHEET_ID"]

# Storage backend selection. Keep Google Sheets by default and switch to
# PostgreSQL later by setting DATA_BACKEND=postgres.
DATA_BACKEND: str = os.environ.get("DATA_BACKEND", "google_sheets")
DATABASE_URL: str | None = os.environ.get("DATABASE_URL")
PGHOST: str = os.environ.get("PGHOST", "localhost")
PGPORT: int = int(os.environ.get("PGPORT", "5432"))
PGDATABASE: str = os.environ.get("PGDATABASE", "")
PGUSER: str = os.environ.get("PGUSER", "")
PGPASSWORD: str | None = os.environ.get("PGPASSWORD")

# Role name that can run officer-only commands (award loot, add tickets, start/end sessions)
OFFICER_ROLE: str = os.environ.get("OFFICER_ROLE", "Officer")

# Optional channel ID to route normal bot chat into. Set this to a single text channel
# so the bot does not spam every command channel.
BOT_CHANNEL_ID: int | None = (
    int(os.environ["BOT_CHANNEL_ID"]) if os.environ.get("BOT_CHANNEL_ID") else None
)

# SHAFTcoin™ grace period in minutes for brief disconnects during a coin session.
SHAFTCOIN_GRACE_MINUTES: int = int(os.environ.get("SHAFTCOIN_GRACE_MINUTES", "5"))
