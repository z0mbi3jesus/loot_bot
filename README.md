# Quarter Master

Discord bot for tracking event attendance and running session-scoped ticket-weighted loot raffles.

## Overview

This bot currently uses Google Sheets in production. It tracks one session at a time, awards tickets on a timer to members in watched voice channels, and lets officers raffle loot against a specific session ID.

## First-Run Checklist

1. Invite the bot to your Discord server.
2. Choose a backend:
   - Google Sheets (current default)
   - SQLite (local file database)
3. If using Google Sheets: create the sheet, create service account credentials, and place the JSON key in the project root.
4. Copy `.env.example` to `.env` and fill in values for your selected backend.
5. Activate the virtual environment.
6. Install dependencies with `python -m pip install -r requirements.txt`.
7. Run `python bot.py`.

## What It Does

- Awards 1 ticket every 30 minutes to members present in watched voice channels.
- Starts and ends loot sessions with attendee snapshots.
- Runs weighted raffles where more tickets increase odds within a single session.
- Logs sessions, session tickets, and loot outcomes to Google Sheets.

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
- `sheets.py` - Google Sheets storage backend
- `sqlite_storage.py` - SQLite storage backend for migration/testing
- `cogs/attendance.py` - Session start/end and attendance commands
- `cogs/loot.py` - Weighted raffle command
- `cogs/dkp.py` - Session ticket lookup and standings commands
- `cogs/ticker.py` - 30-minute ticket loop and watch-channel commands

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

### 4. Configure `.env`

Copy `.env.example` to `.env` and fill in:

- `DISCORD_TOKEN` - Bot token from the Discord Developer Portal
- `GUILD_ID` - Your Discord server ID for fast slash command sync
- `DATA_BACKEND` - Set to `google_sheets` or `sqlite`
- `OFFICER_ROLE` - Role name allowed to run officer-only commands

If `DATA_BACKEND=google_sheets`, also set:

- `SPREADSHEET_ID` - Google Sheet ID from the sheet URL
- `GSPREAD_SERVICE_ACCOUNT_FILE` - Service account JSON file path, usually `service_account.json`

If `DATA_BACKEND=sqlite`, also set:

- `SQLITE_DATABASE_PATH` - Used only when `DATA_BACKEND=sqlite`

### 5. SQLite backend setup (optional path)

If you choose SQLite instead of Google Sheets:

1. Set `DATA_BACKEND=sqlite` in `.env`.
2. Set `SQLITE_DATABASE_PATH` to the desired file path (for example `loot_bot.sqlite3`).
3. Ensure the bot process has write access to that folder.
4. Start the bot. The SQLite file and schema are auto-created on first run.

### Convenience: create the SQLite schema ahead of time

If you want to create the SQLite file and schema on the target machine without starting the bot, run the included helper:

```powershell
python scripts\init_sqlite.py
```

This will create the `loot_bot.sqlite3` file (or the path set in `SQLITE_DATABASE_PATH`) and create the tables `session_tickets`, `sessions`, and `loot_log`.

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
- `/raffle_loot <session_id> <item_name>`
- `/add_tickets <session_id> <member> <amount> [reason]`
- `/add_watch_channel <voice_channel>`
- `/remove_watch_channel <voice_channel>`

### General Commands

- `/attendance`
- `/tickets <session_id> [member]`
- `/standings <session_id> [top]`
- `/watch_channels`

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
- `DATA_BACKEND=sqlite` switches the app to a local SQLite database file.
- The SQLite backend mirrors the same session-based schema, which makes future migration to PostgreSQL or another SQL database much easier.

The backend selection lives in `repository.py`, and the SQLite implementation lives in `sqlite_storage.py`.

## Switch From Google Sheets To SQLite

Use this when you are ready to change the active backend.

1. Stop the bot process.
2. In `.env`, set `DATA_BACKEND=sqlite`.
3. Set `SQLITE_DATABASE_PATH` to the target database file path.
4. Keep Google settings in `.env` if you want an easy rollback, but they will be ignored while SQLite is active.
5. Start the bot with `python bot.py`.
6. Verify startup log shows `Storage backend ready: SQLiteRepository`.
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
