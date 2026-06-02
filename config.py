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

# Role name that can run officer-only commands (award loot, add tickets, start/end sessions)
OFFICER_ROLE: str = os.environ.get("OFFICER_ROLE", "Officer")
