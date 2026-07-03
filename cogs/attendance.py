"""Attendance & session management cog."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from sheets import SheetsClient
from datetime import datetime, timezone, timedelta
from bot_utils import send_bot_message


def _is_officer(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.name == config.OFFICER_ROLE for r in interaction.user.roles)


class Attendance(commands.Cog):
    def __init__(self, bot: commands.Bot, sheets: SheetsClient) -> None:
        self.bot = bot
        self.sheets = sheets
        # Tracks the active session per guild: guild_id -> session_id
        self._active_sessions: dict[int, str] = {}
        # Tracks attendee IDs per active session: guild_id -> list[int]
        self._attendees: dict[int, list[int]] = {}
        # Tracks the active SHAFTcoin™ session per guild: guild_id -> session_id
        self._active_coin_sessions: dict[int, str] = {}
        # Tracks the voice channel for the active SHAFTcoin™ session.
        self._coin_channel_ids: dict[int, int] = {}
        # Tracks attendee IDs per active SHAFTcoin™ session: guild_id -> list[int]
        self._coin_attendees: dict[int, list[int]] = {}
        # Tracks SHAFTcoin™ session member presence state for each guild.
        self._coin_member_state: dict[int, dict[int, dict[str, object]]] = {}

    # ------------------------------------------------------------------
    # /start_session
    # ------------------------------------------------------------------

    @app_commands.command(
        name="start_session",
        description="Snapshot the voice channel and start a loot session (Officer only).",
    )
    @app_commands.describe(
        voice_channel="The voice channel to snapshot attendees from.",
    )
    async def start_session(
        self,
        interaction: discord.Interaction,
        voice_channel: discord.VoiceChannel,
    ) -> None:
        await interaction.response.defer(ephemeral=False)

        if not _is_officer(interaction):
            await send_bot_message(
                interaction,
                content=f"Only members with the **{config.OFFICER_ROLE}** role can start sessions.",
                ephemeral=True,
            )
            return

        guild_id = interaction.guild_id
        if guild_id in self._active_sessions:
            await send_bot_message(
                interaction,
                content=(
                    f"A session is already active (`{self._active_sessions[guild_id]}`). "
                    "End it with `/end_session` first."
                ),
                ephemeral=True,
            )
            return

        members = [m for m in voice_channel.members if not m.bot]
        if not members:
            await send_bot_message(
                interaction,
                content=f"No non-bot members found in **{voice_channel.name}**.",
                ephemeral=True,
            )
            return

        attendee_ids = [m.id for m in members]
        session_id = self.sheets.start_session(
            voice_channel=voice_channel.name,
            attendee_ids=attendee_ids,
        )

        self._active_sessions[guild_id] = session_id
        self._attendees[guild_id] = attendee_ids

        names = "\n".join(f"• {m.display_name}" for m in members)
        embed = discord.Embed(
            title="Session Started",
            color=discord.Color.green(),
        )
        embed.add_field(name="Session ID", value=f"`{session_id}`", inline=True)
        embed.add_field(name="Channel", value=voice_channel.name, inline=True)
        embed.add_field(
            name=f"Attendees ({len(members)})",
            value=names or "None",
            inline=False,
        )
        await send_bot_message(interaction, embed=embed)

    # ------------------------------------------------------------------
    # /end_session
    # ------------------------------------------------------------------

    @app_commands.command(
        name="end_session",
        description="Close the active loot session (Officer only).",
    )
    async def end_session(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=False)

        if not _is_officer(interaction):
            await send_bot_message(
                interaction,
                content=f"Only members with the **{config.OFFICER_ROLE}** role can end sessions.",
                ephemeral=True,
            )
            return

        guild_id = interaction.guild_id
        session_id = self._active_sessions.pop(guild_id, None)
        self._attendees.pop(guild_id, None)

        if session_id is None:
            await send_bot_message(
                interaction, content="There is no active session in this server.", ephemeral=True
            )
            return

        self.sheets.end_session(session_id)

        embed = discord.Embed(
            title="Session Ended",
            description=f"Session `{session_id}` has been closed and logged to Google Sheets.",
            color=discord.Color.red(),
        )
        await send_bot_message(interaction, embed=embed)

    # ------------------------------------------------------------------
    # /start_coin_session
    # ------------------------------------------------------------------

    @app_commands.command(
        name="start_coin_session",
        description="Snapshot the voice channel and start a SHAFTcoin™ session (Officer only).",
    )
    @app_commands.describe(
        voice_channel="The voice channel to snapshot attendees from.",
    )
    async def start_coin_session(
        self,
        interaction: discord.Interaction,
        voice_channel: discord.VoiceChannel,
    ) -> None:
        await interaction.response.defer(ephemeral=False)

        if not _is_officer(interaction):
            await send_bot_message(
                interaction,
                content=f"Only members with the **{config.OFFICER_ROLE}** role can start SHAFTcoin™ sessions.",
                ephemeral=True,
            )
            return

        guild_id = interaction.guild_id
        if guild_id in self._active_coin_sessions:
            await send_bot_message(
                interaction,
                content=(
                    f"A SHAFTcoin™ session is already active (`{self._active_coin_sessions[guild_id]}`). "
                    "End it with `/stop_coin_session` first."
                ),
                ephemeral=True,
            )
            return

        members = [m for m in voice_channel.members if not m.bot]
        if not members:
            await send_bot_message(
                interaction,
                content=f"No non-bot members found in **{voice_channel.name}**.",
                ephemeral=True,
            )
            return

        attendee_ids = [m.id for m in members]
        session_id = self.sheets.start_coin_session(
            voice_channel=voice_channel.name,
            attendee_ids=attendee_ids,
        )

        self._active_coin_sessions[guild_id] = session_id
        self._coin_channel_ids[guild_id] = voice_channel.id
        self._coin_attendees[guild_id] = attendee_ids
        now = datetime.now(timezone.utc)
        self._coin_member_state[guild_id] = {
            m.id: {
                "checkpoint_start": now,
                "ineligible": False,
                "last_seen": now,
                "present": True,
            }
            for m in members
        }

        names = "\n".join(f"• {m.display_name}" for m in members)
        embed = discord.Embed(
            title="SHAFTcoin™ Session Started",
            color=discord.Color.green(),
        )
        embed.add_field(name="Session ID", value=f"`{session_id}`", inline=True)
        embed.add_field(name="Channel", value=voice_channel.name, inline=True)
        embed.add_field(
            name=f"Attendees ({len(members)})",
            value=names or "None",
            inline=False,
        )
        await send_bot_message(interaction, embed=embed)

    # ------------------------------------------------------------------
    # /stop_coin_session
    # ------------------------------------------------------------------

    @app_commands.command(
        name="stop_coin_session",
        description="Close the active SHAFTcoin™ session (Officer only).",
    )
    async def stop_coin_session(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=False)

        if not _is_officer(interaction):
            await send_bot_message(
                interaction,
                content=f"Only members with the **{config.OFFICER_ROLE}** role can stop SHAFTcoin™ sessions.",
                ephemeral=True,
            )
            return

        guild_id = interaction.guild_id
        session_id = self._active_coin_sessions.pop(guild_id, None)
        self._coin_channel_ids.pop(guild_id, None)
        self._coin_attendees.pop(guild_id, None)
        self._coin_member_state.pop(guild_id, None)

        if session_id is None:
            await send_bot_message(
                interaction, content="There is no active SHAFTcoin™ session in this server.", ephemeral=True
            )
            return

        self.sheets.end_coin_session(session_id)

        embed = discord.Embed(
            title="SHAFTcoin™ Session Ended",
            description=f"SHAFTcoin™ session `{session_id}` has been closed and logged.",
            color=discord.Color.red(),
        )
        await send_bot_message(interaction, embed=embed)

    # ------------------------------------------------------------------
    # /attendance
    # ------------------------------------------------------------------

    @app_commands.command(
        name="attendance",
        description="Show attendees for the current active session.",
    )
    async def attendance(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        session_id = self._active_sessions.get(guild_id)
        if session_id is None:
            await send_bot_message(interaction, content="No session is currently active.", ephemeral=True)
            return

        attendee_ids = self._attendees.get(guild_id, [])
        lines: list[str] = []
        for uid in attendee_ids:
            member = interaction.guild.get_member(uid)
            lines.append(f"• {member.display_name if member else uid}")

        embed = discord.Embed(
            title=f"Attendance — Session `{session_id}`",
            description="\n".join(lines) or "No attendees recorded.",
            color=discord.Color.blue(),
        )
        await send_bot_message(interaction, embed=embed)

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        guild_id = member.guild.id
        if guild_id not in self._active_coin_sessions:
            return

        coin_channel_id = self._coin_channel_ids.get(guild_id)
        if coin_channel_id is None:
            return

        if before.channel is not None and before.channel.id == coin_channel_id:
            if after.channel is None or after.channel.id != coin_channel_id:
                state = self._coin_member_state.setdefault(guild_id, {}).get(member.id)
                if state is None:
                    return
                state["present"] = False
                state["last_seen"] = datetime.now(timezone.utc)

        if after.channel is not None and after.channel.id == coin_channel_id:
            now = datetime.now(timezone.utc)
            state = self._coin_member_state.setdefault(guild_id, {}).get(member.id)
            if state is None:
                self._coin_member_state.setdefault(guild_id, {})[member.id] = {
                    "checkpoint_start": now,
                    "ineligible": False,
                    "last_seen": now,
                    "present": True,
                }
                self._coin_attendees.setdefault(guild_id, []).append(member.id)
                return

            if not state["present"]:
                absent_duration = now - state["last_seen"]
                if absent_duration <= timedelta(minutes=config.SHAFTCOIN_GRACE_MINUTES):
                    state["present"] = True
                    state["last_seen"] = now
                else:
                    state["present"] = True
                    state["last_seen"] = now
                    state["checkpoint_start"] = now
                    state["ineligible"] = False
    def get_active_session(self, guild_id: int) -> str | None:
        return self._active_sessions.get(guild_id)

    def get_attendee_ids(self, guild_id: int) -> list[int]:
        return self._attendees.get(guild_id, [])

    def get_active_coin_session(self, guild_id: int) -> str | None:
        return self._active_coin_sessions.get(guild_id)

    def get_coin_session_channel_id(self, guild_id: int) -> int | None:
        return self._coin_channel_ids.get(guild_id)

    def get_all_active_coin_sessions(self) -> dict[int, tuple[str, int]]:
        return {
            guild_id: (session_id, self._coin_channel_ids[guild_id])
            for guild_id, session_id in self._active_coin_sessions.items()
            if guild_id in self._coin_channel_ids
        }

    def get_coin_session_attendees(self, guild_id: int) -> list[int]:
        return self._coin_attendees.get(guild_id, [])

    def get_coin_member_state(self, guild_id: int) -> dict[int, dict[str, object]]:
        return self._coin_member_state.get(guild_id, {})


async def setup(bot: commands.Bot, sheets: SheetsClient) -> None:
    await bot.add_cog(Attendance(bot, sheets))
