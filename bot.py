"""Loot Bot — main entry point."""

from __future__ import annotations

import logging
import sys

import discord
from discord.ext import commands

import config
from sheets import SheetsClient
from cogs import attendance, loot, dkp, ticker

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("loot_bot")

# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.members = True          # Required to read voice channel members
intents.voice_states = True     # Required to snapshot voice channel state


class LootBot(commands.Bot):
    def __init__(self, sheets_client: SheetsClient) -> None:
        super().__init__(command_prefix="!", intents=intents)
        self.sheets = sheets_client

    async def setup_hook(self) -> None:
        guild = discord.Object(id=config.GUILD_ID)

        await attendance.setup(self, self.sheets)
        await loot.setup(self, self.sheets)
        await dkp.setup(self, self.sheets)
        await ticker.setup(self, self.sheets)

        # Sync slash commands to the configured guild for instant availability.
        # Use bot.tree.sync() (no guild arg) to sync globally (takes ~1 hour).
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        log.info("Synced %d slash command(s) to guild %s.", len(synced), config.GUILD_ID)

    async def on_ready(self) -> None:
        assert self.user is not None
        log.info("Logged in as %s (id=%s)", self.user, self.user.id)
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="loot drop",
            )
        )


def main() -> None:
    log.info("Connecting to Google Sheets...")
    sheets_client = SheetsClient()
    log.info("Google Sheets ready.")

    bot = LootBot(sheets_client)
    bot.run(config.DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
