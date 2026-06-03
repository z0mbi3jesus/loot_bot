# Quarter Master

Discord bot for tracking event attendance and running session-scoped ticket-weighted loot raffles.

## What It Does

- Awards 1 raffle ticket every 30 minutes to members present in watched voice channels.
- Starts and ends loot sessions with attendee snapshots.
- Runs weighted raffles where more tickets increase odds within a single session.
- Logs sessions, session tickets, and loot outcomes to Google Sheets.

## Tech Stack

- Python 3.13+
- discord.py (slash commands)
- gspread + Google Service Account
- Google Sheets as storage

## Project Structure

- `bot.py` - Bot entrypoint, startup, and command sync
- `config.py` - Environment variable loading
- `sheets.py` - Google Sheets data access layer
- `cogs/attendance.py` - Session start/end and attendance commands
- `cogs/loot.py` - Weighted raffle command
- `cogs/dkp.py` - Session ticket lookup and standings commands
- `cogs/ticker.py` - 30-minute ticket loop and watch-channel commands
- `bot_config.json` - Local persisted watched channels (ignored by git)

## Prerequisites

- A Discord bot application invited to your test server
- Google Cloud project with:
  - Google Sheets API enabled
  - Google Drive API enabled
  - Service Account JSON key downloaded
- A Google Sheet shared with the service account email as Editor

## Environment Variables

Create `.env` from `.env.example` and set:

- `DISCORD_TOKEN` - Bot token from Discord Developer Portal
- `GUILD_ID` - Target Discord server ID for fast guild command sync
- `SPREADSHEET_ID` - Google Sheet ID from the sheet URL
- `GSPREAD_SERVICE_ACCOUNT_FILE` - Service account JSON file path (for example `service_account.json`)
- `OFFICER_ROLE` - Role name allowed to run officer-only commands

## Install and Run

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python bot.py
```

Expected startup lines include:

- Connecting to Google Sheets
- Google Sheets ready
- Synced commands to your guild
- Logged in as <bot name>

## Slash Commands

### Officer Commands

- `/start_session <voice_channel>`
- `/end_session`
- `/raffle_loot <session_id> <item_name>`
- `/add_tickets <session_id> <member> <amount> [reason]`
- `/add_watch_channel <voice_channel>`
- `/remove_watch_channel <voice_channel>`

### General Commands

- `/attendance`
- `/tickets <session_id> [member]`
- `/standings <session_id> [top]`
- `/watch_channels`

## Data Model (Google Sheets)

Worksheets are auto-created on first successful run:

- `session_tickets`: `session_id | discord_id | name | tickets`
- `sessions`: `session_id | start_time | end_time | voice_channel | attendees`
- `loot_log`: `timestamp | session_id | item_name | winner_id | winner_name | winner_tickets`

## Testing Flow (Quick)

1. Start bot.
2. Run `/add_watch_channel` for your event voice channel.
3. Confirm with `/watch_channels`.
4. Start a session with `/start_session`.
5. Wait for a 30-minute tick, then verify with `/tickets <session_id>`.
6. Run `/raffle_loot <session_id> <test_item>`.
7. End session with `/end_session`.

## Git Notes

Sensitive/local files are intentionally ignored:

- `.env`
- `service_account.json`
- `.venv/`
- `bot_config.json`

## Troubleshooting

- Missing `GUILD_ID`: ensure `.env` exists in project root and contains `GUILD_ID=<server_id>`
- Service account file not found: verify `GSPREAD_SERVICE_ACCOUNT_FILE` points to a real file
- Commands not visible: ensure bot is invited to the same server as `GUILD_ID`, then restart bot

## Contact

- Discord: `z0mbi3jesus`
- Email: `hnlebowski@gmail.com`
