"""Session ticket viewing and management cog."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from sheets import SheetsClient
from bot_utils import send_bot_message


def _is_officer(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.name == config.OFFICER_ROLE for r in interaction.user.roles)


class DKP(commands.Cog):
    def __init__(self, bot: commands.Bot, sheets: SheetsClient) -> None:
        self.bot = bot
        self.sheets = sheets

    # ------------------------------------------------------------------
    # /tickets
    # ------------------------------------------------------------------

    @app_commands.command(
        name="tickets",
        description="Check ticket count for a specific session.",
    )
    @app_commands.describe(
        session_id="The session ID to inspect.",
        member="The member to look up (defaults to you).",
    )
    async def tickets(
        self,
        interaction: discord.Interaction,
        session_id: str,
        member: discord.Member | None = None,
    ) -> None:
        target = member or interaction.user
        record = self.sheets.get_session_tickets(session_id, target.id)

        if record is None:
            await send_bot_message(
                interaction,
                content=f"No ticket record found for **{target.display_name}** in session `{session_id}`.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Session Tickets",
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Member", value=target.mention, inline=True)
        embed.add_field(name="Session", value=f"`{session_id}`", inline=True)
        embed.add_field(
            name="Tickets",
            value=str(record["tickets"]),
            inline=True,
        )
        await send_bot_message(interaction, embed=embed)

    # ------------------------------------------------------------------
    # /standings
    # ------------------------------------------------------------------

    @app_commands.command(
        name="standings",
        description="Show the top ticket holders for a session.",
    )
    @app_commands.describe(
        session_id="The session ID to inspect.",
        top="How many members to show (max 25, default 15).",
    )
    async def standings(
        self, interaction: discord.Interaction, session_id: str, top: int = 15
    ) -> None:
        top = min(max(1, top), 25)
        records = self.sheets.get_session_ticket_standings(session_id, top_n=top)

        if not records:
            await send_bot_message(
                interaction, content=f"No ticket records found for session `{session_id}`.", ephemeral=True
            )
            return

        lines: list[str] = []
        for i, rec in enumerate(records, start=1):
            lines.append(f"`{i:>2}.` **{rec['name']}** - {rec['tickets']} ticket(s)")

        embed = discord.Embed(
            title="Session Ticket Standings",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await send_bot_message(interaction, embed=embed)

    # ------------------------------------------------------------------
    # /add_tickets  (officer only)
    # ------------------------------------------------------------------

    @app_commands.command(
        name="add_tickets",
        description="Manually add or remove tickets for a member in a session (Officer only).",
    )
    @app_commands.describe(
        session_id="The session ID to adjust.",
        member="The member to adjust.",
        amount="Tickets to add (use negative to deduct).",
        reason="Optional reason shown in the confirmation message.",
    )
    async def add_tickets(
        self,
        interaction: discord.Interaction,
        session_id: str,
        member: discord.Member,
        amount: int,
        reason: str = "Manual adjustment",
    ) -> None:
        await interaction.response.defer(ephemeral=False)

        if not _is_officer(interaction):
            await send_bot_message(
                interaction,
                content=f"Only members with the **{config.OFFICER_ROLE}** role can adjust tickets.",
                ephemeral=True,
            )
            return

        new_total = self.sheets.upsert_session_member(
            session_id,
            member.id,
            member.display_name,
            tickets_delta=amount,
        )
        action = f"+{amount}" if amount >= 0 else str(amount)

        embed = discord.Embed(
            title="Session Tickets Adjusted",
            color=discord.Color.green() if amount >= 0 else discord.Color.red(),
        )
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="Session", value=f"`{session_id}`", inline=True)
        embed.add_field(name="Change", value=action, inline=True)
        embed.add_field(name="New Total", value=str(new_total), inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await send_bot_message(interaction, embed=embed)


async def setup(bot: commands.Bot, sheets: SheetsClient) -> None:
    await bot.add_cog(DKP(bot, sheets))
