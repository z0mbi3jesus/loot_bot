"""Attendance & session management cog."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from sheets import SheetsClient


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
            await interaction.followup.send(
                f"Only members with the **{config.OFFICER_ROLE}** role can start sessions.",
                ephemeral=True,
            )
            return

        guild_id = interaction.guild_id
        if guild_id in self._active_sessions:
            await interaction.followup.send(
                f"A session is already active (`{self._active_sessions[guild_id]}`). "
                "End it with `/end_session` first.",
                ephemeral=True,
            )
            return

        if dkp_reward <= 0:
            dkp_reward = config.DEFAULT_SESSION_DKP

        members = [m for m in voice_channel.members if not m.bot]
        if not members:
            await interaction.followup.send(
                f"No non-bot members found in **{voice_channel.name}**.", ephemeral=True
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
        await interaction.followup.send(embed=embed)

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
            await interaction.followup.send(
                f"Only members with the **{config.OFFICER_ROLE}** role can end sessions.",
                ephemeral=True,
            )
            return

        guild_id = interaction.guild_id
        session_id = self._active_sessions.pop(guild_id, None)
        self._attendees.pop(guild_id, None)

        if session_id is None:
            await interaction.followup.send(
                "There is no active session in this server.", ephemeral=True
            )
            return

        self.sheets.end_session(session_id)

        embed = discord.Embed(
            title="Session Ended",
            description=f"Session `{session_id}` has been closed and logged to Google Sheets.",
            color=discord.Color.red(),
        )
        await interaction.followup.send(embed=embed)

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
            await interaction.response.send_message(
                "No session is currently active.", ephemeral=True
            )
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
        await interaction.response.send_message(embed=embed)

    def get_active_session(self, guild_id: int) -> str | None:
        return self._active_sessions.get(guild_id)

    def get_attendee_ids(self, guild_id: int) -> list[int]:
        return self._attendees.get(guild_id, [])


async def setup(bot: commands.Bot, sheets: SheetsClient) -> None:
    await bot.add_cog(Attendance(bot, sheets))
