# Quarter Master

Discord bot for tracking event attendance and running session-scoped ticket-weighted loot raffles.

## Overview

This bot tracks event attendance, runs session-scoped ticket-weighted loot raffles, and includes a separate in-bot economy called SHAFTcoin™. The project now targets PostgreSQL as the primary production backend (Google Sheets remains supported for small deployments).

## First-Run Checklist

1. Invite the bot to your Discord server.
2. Choose a backend:
   - Google Sheets (current default)
   - PostgreSQL
3. If using Google Sheets: create the sheet, create service account credentials, and place the JSON key in the project root.
4. Copy `.env.example` to `.env` and fill in values for your selected backend.
5. Activate the virtual environment.
6. Install dependencies with `python -m pip install -r requirements.txt`.
7. Run `python bot.py`.

## What It Does

- Awards 1 ticket every 30 minutes to members present in watched voice channels.
- Tracks a separate SHAFTcoin™ economy: officers can start/stop coin sessions and members earn coin on a 30-minute checkpoint with a 5-minute reconnect grace window.
- Starts and ends loot sessions with attendee snapshots.
- Runs weighted raffles where more tickets increase odds within a single session.
- Provides an officer-managed purchase request workflow for spending SHAFTcoin™ (create, approve, deny).
- Routes bot responses into an optional dedicated channel via `BOT_CHANNEL_ID` for centralized bot chatter.
- Stores session, ticket, loot, coin balances, transactions, and purchase requests in PostgreSQL (or Google Sheets when configured).

## Requirements

- Windows, macOS, or Linux with Python 3.13+
- A Discord bot application invited to your test server
- A Google Cloud project with:
  - Google Sheets API enabled
  - Google Drive API enabled
  - A downloaded Service Account JSON key
- A Google Sheet shared with the service account email as Editor

## Project Structure

- `bot.py` - Bot entrypoint, startup, and command sync
- `config.py` - Environment variable loading
- `repository.py` - Storage backend selection
- `storage.py` - Repository interface (storage abstraction)
- `sheets.py` - Google Sheets storage backend
- `postgres_storage.py` - PostgreSQL storage backend
- `bot_utils.py` - Centralized helper for routing bot messages to `BOT_CHANNEL_ID`
- `scripts/init_postgres.py` - Helper to initialize the Postgres schema
- `cogs/attendance.py` - Session start/end and attendance commands
- `cogs/loot.py` - Weighted raffle command
- `cogs/dkp.py` - Session ticket lookup and standings commands
- `cogs/ticker.py` - 30-minute ticket loop and watch-channel commands
- `cogs/purchases.py` - Purchase request and approval workflow

## Setup Steps

### 1. Invite the bot to your server

In the Discord Developer Portal:

1. Open your application.
2. Go to OAuth2 > URL Generator.
3. Select scopes:
   - `bot`
   - `applications.commands`
4. Select the permissions the bot needs, at minimum:
   - View Channels
   - Send Messages
   - Embed Links
   - Read Message History
   - Connect if you want it to read voice channel membership
5. Open the generated URL.
6. Choose your test server.
7. Authorize.

### 2. Create the Google Sheet

1. Create a new Google Sheet.
2. Copy the spreadsheet ID from the URL.
3. Share the sheet with the service account email from your JSON key.

### 3. Prepare the Google Cloud credentials

1. Create or use a Google Cloud project.
2. Enable Google Sheets API and Google Drive API.
3. Create a Service Account.
4. Create and download a JSON key.
5. Place that JSON file in the project root.

or set:
### 4. Configure `.env`

Copy `.env.example` to `.env` and fill in:

- `DISCORD_TOKEN` - Bot token from the Discord Developer Portal
- `GUILD_ID` - Your Discord server ID for fast slash command sync
- `DATA_BACKEND` - Set to `google_sheets` or `postgres` (recommended)
- `OFFICER_ROLE` - Role name allowed to run officer-only commands
- `BOT_CHANNEL_ID` - Optional: channel ID where the bot posts normal replies (keeps command channels clean)

If `DATA_BACKEND=google_sheets`, also set:

- `SPREADSHEET_ID` - Google Sheet ID from the sheet URL
- `GSPREAD_SERVICE_ACCOUNT_FILE` - Service account JSON file path, usually `service_account.json`

If `DATA_BACKEND=postgres`, also set:

- `DATABASE_URL` - PostgreSQL connection string (preferred)

or set:

- `PGHOST`
- `PGPORT`
- `PGDATABASE`
- `PGUSER`
- `PGPASSWORD`

### 5. PostgreSQL backend setup (optional path)

If you choose PostgreSQL instead of Google Sheets:

1. Set `DATA_BACKEND=postgres` in `.env`.
2. Set `DATABASE_URL` or the individual `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, and `PGPASSWORD` values.
3. Ensure the bot can connect to the PostgreSQL server from the host where it runs.
4. Start the bot. The database schema is auto-created on first run.

### Convenience: create the PostgreSQL schema ahead of time

If you want to create the PostgreSQL schema on the target machine without starting the bot, run the included helper:

```powershell
python scripts\init_postgres.py
```

This will connect to PostgreSQL using your `.env` settings and create the tables `session_tickets`, `sessions`, `coin_sessions`, `shaftcoin_balances`, `shaftcoin_transactions`, `purchase_requests`, and `loot_log`.

## Install and Run

1. Open a terminal in the project folder.
2. Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

4. Start the bot:

```powershell
python bot.py
```

Expected startup lines include:

- Storage backend ready
- Synced slash commands to your guild
- Logged in as <bot name>

## Slash Commands

### Officer Commands

- `/start_session <voice_channel>`
- `/end_session`
- `/start_coin_session <voice_channel>`
- `/stop_coin_session`
- `/raffle_loot <session_id> <item_name>`
- `/add_tickets <session_id> <member> <amount> [reason]`
- `/create_purchase_request <amount> <description>`
- `/approve_purchase <request_id> <reason?>`
- `/deny_purchase <request_id> <reason?>`
- `/add_watch_channel <voice_channel>`
- `/remove_watch_channel <voice_channel>`

### General Commands

- `/attendance`
- `/tickets <session_id> [member]`
- `/standings <session_id> [top]`
- `/watch_channels`
- `/balance [member]` - Show SHAFTcoin™ balance
- `/request_purchase <amount> <description>` - Create a purchase request (officer approval required)

## Google Sheets Data Model

The bot auto-creates these worksheets if they do not already exist:

- `session_tickets`: `session_id | discord_id | name | tickets`
- `sessions`: `session_id | start_time | end_time | voice_channel | attendees`
- `loot_log`: `timestamp | session_id | item_name | winner_id | winner_name | winner_tickets`

## Testing Flow

1. Start the bot.
2. Run `/add_watch_channel` for the voice channel you want to monitor.
3. Confirm with `/watch_channels`.
4. Start a session with `/start_session`.
5. Wait for a 30-minute tick.
6. Check ticket totals with `/tickets <session_id>`.
7. Run `/raffle_loot <session_id> <test_item>`.
8. End the session with `/end_session`.

## Database Migration Prep

The bot now uses a repository factory instead of depending directly on Google Sheets.

- `DATA_BACKEND=google_sheets` keeps the current live behavior.
- `DATA_BACKEND=postgres` switches the app to PostgreSQL.

The backend selection lives in `repository.py`, and the PostgreSQL implementation lives in `postgres_storage.py`.

## Switch From Google Sheets To PostgreSQL

Use this when you are ready to change the active backend.

1. Stop the bot process.
2. In `.env`, set `DATA_BACKEND=postgres`.
3. Set `DATABASE_URL` or the individual Postgres `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, and `PGPASSWORD` values.
4. Keep Google settings in `.env` if you want an easy rollback, but they will be ignored while Postgres is active.
5. Start the bot with `python bot.py`.
6. Verify startup log shows `Storage backend ready: PostgresRepository`.
7. Run a quick smoke test:
   - `/start_session`
   - `/add_watch_channel`
   - `/tickets <session_id>`
   - `/raffle_loot <session_id> <item_name>`
8. If anything fails, switch `DATA_BACKEND` back to `google_sheets` and restart.

## Git Notes

Sensitive and local files are intentionally ignored:

- `.env`
- `service_account.json`
- `.venv/`
- `bot_config.json`

## Troubleshooting

- Missing `GUILD_ID`: ensure `.env` exists in the project root and contains `GUILD_ID=<server_id>`.
- Service account file not found: verify `GSPREAD_SERVICE_ACCOUNT_FILE` points to a real file.
- Commands not visible: ensure the bot is invited to the same server as `GUILD_ID`, then restart the bot.

## Contact

- Discord: `z0mbi3jesus`
- Email: `hnlebowski@gmail.com`
