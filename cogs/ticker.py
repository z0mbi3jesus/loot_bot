"""
Ticker cog — awards 1 raffle ticket every 30 minutes to members
present in any watched voice channel.

Officer commands:
  /add_watch_channel    — add a voice channel to the watch list
  /remove_watch_channel — remove a voice channel from the watch list
  /watch_channels       — list currently monitored channels
"""

from __future__ import annotations

import json
import logging
import os
from datetime import timedelta
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from sheets import SheetsClient
from cogs.attendance import Attendance
from bot_utils import send_bot_message

log = logging.getLogger("quarter_master.ticker")

_CONFIG_FILE = "bot_config.json"
_TICK_MINUTES = 30


def _is_officer(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.name == config.OFFICER_ROLE for r in interaction.user.roles)


def _load_config() -> dict[str, Any]:
    if os.path.exists(_CONFIG_FILE):
        with open(_CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_config(data: dict[str, Any]) -> None:
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class Ticker(commands.Cog):
    """Background ticker that awards 1 ticket per 30-minute window."""

    def __init__(self, bot: commands.Bot, sheets: SheetsClient) -> None:
        self.bot = bot
        self.sheets = sheets
        # guild_id (int) -> list of voice channel IDs (int)
        self._watched: dict[int, list[int]] = self._load_watched()
        self.tick.start()

    def cog_unload(self) -> None:
        self.tick.cancel()

    def _get_attendance_cog(self) -> Attendance | None:
        return self.bot.cogs.get("Attendance")  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load_watched(self) -> dict[int, list[int]]:
        data = _load_config()
        raw = data.get("watched_channels", {})
        return {int(gid): [int(cid) for cid in cids] for gid, cids in raw.items()}

    def _save_watched(self) -> None:
        data = _load_config()
        data["watched_channels"] = {
            str(gid): [str(cid) for cid in cids]
            for gid, cids in self._watched.items()
        }
        _save_config(data)

    # ------------------------------------------------------------------
    # Background task
    # ------------------------------------------------------------------

    @tasks.loop(minutes=_TICK_MINUTES)
    async def tick(self) -> None:
        log.info("Ticker fired — scanning watched channels.")
        attendance_cog = self._get_attendance_cog()
        for guild_id, channel_ids in self._watched.items():
            session_id = attendance_cog.get_active_session(guild_id) if attendance_cog else None
            if session_id is None:
                continue

            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue

            awarded: set[int] = set()
            for channel_id in channel_ids:
                channel = guild.get_channel(channel_id)
                if not isinstance(channel, discord.VoiceChannel):
                    continue
                for member in channel.members:
                    if member.bot or member.id in awarded:
                        continue
                    new_total = self.sheets.upsert_session_member(
                        session_id,
                        member.id,
                        member.display_name,
                        tickets_delta=1,
                    )
                    awarded.add(member.id)
                    log.debug(
                        "Awarded 1 ticket to %s (%s) for session %s → total %s",
                        member.display_name,
                        member.id,
                        session_id,
                        new_total,
                    )

            if awarded:
                log.info(
                    "Guild %s: awarded 1 ticket to %d member(s).", guild_id, len(awarded)
                )

        # SHAFTcoin™ reward loop
        for guild_id, (session_id, coin_channel_id) in (
            attendance_cog.get_all_active_coin_sessions().items() if attendance_cog else []
        ):
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue

            member_states = attendance_cog.get_coin_member_state(guild_id)
            if not member_states:
                continue

            awarded_coin: set[int] = set()
            now = discord.utils.utcnow()
            for member_id, state in member_states.items():
                checkpoint_start = state.get("checkpoint_start")
                present = state.get("present", False)
                last_seen = state.get("last_seen")

                if checkpoint_start is None or last_seen is None:
                    continue

                if not present:
                    if now - last_seen > timedelta(minutes=config.SHAFTCOIN_GRACE_MINUTES):
                        state["checkpoint_start"] = now
                    continue

                if now - checkpoint_start < timedelta(minutes=_TICK_MINUTES):
                    continue

                member = guild.get_member(member_id)
                display_name = member.display_name if member else str(member_id)
                new_balance = self.sheets.adjust_shaftcoin_balance(
                    member_id,
                    display_name,
                    1,
                    "earn",
                    "SHAFTcoin™ earned for 30-minute DAO voice session",
                    session_id,
                )
                state["checkpoint_start"] = now
                awarded_coin.add(member_id)
                log.debug(
                    "Awarded 1 SHAFTcoin™ to %s (%s) for coin session %s → balance %s",
                    display_name,
                    member_id,
                    session_id,
                    new_balance,
                )

            if awarded_coin:
                log.info(
                    "Guild %s: awarded 1 SHAFTcoin™ to %d member(s).", guild_id, len(awarded_coin)
                )

    @tick.before_loop
    async def before_tick(self) -> None:
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # /add_watch_channel
    # ------------------------------------------------------------------

    @app_commands.command(
        name="add_watch_channel",
        description="Add a voice channel to the 30-min ticket ticker (Officer only).",
    )
    @app_commands.describe(channel="The voice channel to start watching.")
    async def add_watch_channel(
        self, interaction: discord.Interaction, channel: discord.VoiceChannel
    ) -> None:
        if not _is_officer(interaction):
            await send_bot_message(
                interaction,
                content=f"Only members with the **{config.OFFICER_ROLE}** role can configure channels.",
                ephemeral=True,
            )
            return

        guild_id = interaction.guild_id
        watched = self._watched.setdefault(guild_id, [])
        if channel.id in watched:
            await send_bot_message(
                interaction, content=f"**{channel.name}** is already being watched.", ephemeral=True
            )
            return

        watched.append(channel.id)
        self._save_watched()
        await send_bot_message(
            interaction,
            content=(
                f"Now watching **{channel.name}** — members will earn 1 ticket every "
                f"{_TICK_MINUTES} minutes while present."
            ),
        )

    # ------------------------------------------------------------------
    # /remove_watch_channel
    # ------------------------------------------------------------------

    @app_commands.command(
        name="remove_watch_channel",
        description="Remove a voice channel from the ticker watch list (Officer only).",
    )
    @app_commands.describe(channel="The voice channel to stop watching.")
    async def remove_watch_channel(
        self, interaction: discord.Interaction, channel: discord.VoiceChannel
    ) -> None:
        if not _is_officer(interaction):
            await send_bot_message(
                interaction,
                content=f"Only members with the **{config.OFFICER_ROLE}** role can configure channels.",
                ephemeral=True,
            )
            return

        guild_id = interaction.guild_id
        watched = self._watched.get(guild_id, [])
        if channel.id not in watched:
            await send_bot_message(
                interaction, content=f"**{channel.name}** is not in the watch list.", ephemeral=True
            )
            return

        watched.remove(channel.id)
        self._save_watched()
        await send_bot_message(interaction, content=f"Stopped watching **{channel.name}**.")

    # ------------------------------------------------------------------
    # /watch_channels
    # ------------------------------------------------------------------

    @app_commands.command(
        name="watch_channels",
        description="List the voice channels currently being watched for ticket ticks.",
    )
    async def watch_channels(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        channel_ids = self._watched.get(guild_id, [])

        if not channel_ids:
            await send_bot_message(
                interaction,
                content="No channels are being watched yet. Use `/add_watch_channel` to add one.",
                ephemeral=True,
            )
            return

        lines: list[str] = []
        for cid in channel_ids:
            ch = interaction.guild.get_channel(cid)
            lines.append(f"• {ch.name if ch else f'Unknown ({cid})'}")

        embed = discord.Embed(
            title=f"Watched Channels (tick every {_TICK_MINUTES} min)",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        await send_bot_message(interaction, embed=embed)


async def setup(bot: commands.Bot, sheets: SheetsClient) -> None:
    await bot.add_cog(Ticker(bot, sheets))
