"""Ticket viewing and management cog."""

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


class DKP(commands.Cog):
    def __init__(self, bot: commands.Bot, sheets: SheetsClient) -> None:
        self.bot = bot
        self.sheets = sheets

    # ------------------------------------------------------------------
    # /tickets
    # ------------------------------------------------------------------

    @app_commands.command(
        name="tickets",
        description="Check your raffle ticket balance (or another member's).",
    )
    @app_commands.describe(member="The member to look up (defaults to you).")
    async def tickets(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        target = member or interaction.user
        record = self.sheets.get_tickets(target.id)

        embed = discord.Embed(
            title="Raffle Tickets",
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Member", value=target.mention, inline=True)
        embed.add_field(
            name="Tickets",
            value=str(record["tickets"]) if record else "0 (not yet recorded)",
            inline=True,
        )
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------
    # /standings
    # ------------------------------------------------------------------

    @app_commands.command(
        name="standings",
        description="Show the top raffle ticket holders.",
    )
    @app_commands.describe(top="How many members to show (max 25, default 15).")
    async def standings(
        self, interaction: discord.Interaction, top: int = 15
    ) -> None:
        top = min(max(1, top), 25)
        records = self.sheets.get_standings(top_n=top)

        if not records:
            await interaction.response.send_message(
                "No ticket records found yet.", ephemeral=True
            )
            return

        lines: list[str] = []
        for i, rec in enumerate(records, start=1):
            lines.append(f"`{i:>2}.` **{rec['name']}** — {rec['tickets']} ticket(s)")

        embed = discord.Embed(
            title="Ticket Standings",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------
    # /add_tickets  (officer only)
    # ------------------------------------------------------------------

    @app_commands.command(
        name="add_tickets",
        description="Manually add (or remove) tickets for a member (Officer only).",
    )
    @app_commands.describe(
        member="The member to adjust.",
        amount="Tickets to add (use negative to deduct).",
        reason="Optional reason shown in the confirmation message.",
    )
    async def add_tickets(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: int,
        reason: str = "Manual adjustment",
    ) -> None:
        await interaction.response.defer(ephemeral=False)

        if not _is_officer(interaction):
            await interaction.followup.send(
                f"Only members with the **{config.OFFICER_ROLE}** role can adjust tickets.",
                ephemeral=True,
            )
            return

        new_total = self.sheets.upsert_member(member.id, member.display_name, tickets_delta=amount)
        action = f"+{amount}" if amount >= 0 else str(amount)

        embed = discord.Embed(
            title="Tickets Adjusted",
            color=discord.Color.green() if amount >= 0 else discord.Color.red(),
        )
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="Change", value=action, inline=True)
        embed.add_field(name="New Total", value=str(new_total), inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot, sheets: SheetsClient) -> None:
    await bot.add_cog(DKP(bot, sheets))
