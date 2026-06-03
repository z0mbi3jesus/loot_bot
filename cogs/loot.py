"""Loot raffle cog — weighted random draw from session attendees."""

from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands

import config
from sheets import SheetsClient


def _is_officer(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.name == config.OFFICER_ROLE for r in interaction.user.roles)


def _weighted_draw(pool: list[dict]) -> dict:
    """
    Pick one entry from pool using ticket counts as weights.
    Each entry is {member, tickets}. Falls back to uniform random if all
    attendees have 0 tickets (so nobody is locked out forever).
    """
    weights = [max(e["tickets"], 1) for e in pool]
    return random.choices(pool, weights=weights, k=1)[0]


class Loot(commands.Cog):
    def __init__(self, bot: commands.Bot, sheets: SheetsClient) -> None:
        self.bot = bot
        self.sheets = sheets

    # ------------------------------------------------------------------
    # /raffle_loot
    # ------------------------------------------------------------------

    @app_commands.command(
        name="raffle_loot",
        description="Run a weighted raffle for a specific session (Officer only).",
    )
    @app_commands.describe(
        session_id="The session ID to raffle from.",
        item_name="Name of the item being raffled.",
    )
    async def raffle_loot(
        self,
        interaction: discord.Interaction,
        session_id: str,
        item_name: str,
    ) -> None:
        await interaction.response.defer(ephemeral=False)

        if not _is_officer(interaction):
            await interaction.followup.send(
                f"Only members with the **{config.OFFICER_ROLE}** role can run raffles.",
                ephemeral=True,
            )
            return

        session = self.sheets.get_session(session_id)
        if session is None:
            await interaction.followup.send(
                f"Session `{session_id}` was not found.",
                ephemeral=True,
            )
            return

        attendee_ids = self.sheets.get_session_attendees(session_id)
        if not attendee_ids:
            await interaction.followup.send(
                f"No attendees recorded for session `{session_id}`.",
                ephemeral=True,
            )
            return

        # Build weighted pool from session-scoped ticket counts.
        pool: list[dict] = []
        for uid in attendee_ids:
            member = interaction.guild.get_member(uid)
            if member is None:
                continue
            record = self.sheets.get_session_tickets(session_id, uid)
            pool.append({
                "member": member,
                "tickets": record["tickets"] if record else 0,
            })

        if not pool:
            await interaction.followup.send("Could not resolve any attendees.", ephemeral=True)
            return

        result = _weighted_draw(pool)
        winner: discord.Member = result["member"]
        winner_tickets: int = result["tickets"]

        self.sheets.log_loot(
            session_id=session_id,
            item_name=item_name,
            winner_id=winner.id,
            winner_name=winner.display_name,
            winner_tickets=winner_tickets,
        )

        # Build odds summary for transparency
        total_weight = sum(max(e["tickets"], 1) for e in pool)
        odds_lines = []
        for entry in sorted(pool, key=lambda e: e["tickets"], reverse=True):
            pct = max(entry["tickets"], 1) / total_weight * 100
            odds_lines.append(
                f"{'→ ' if entry['member'].id == winner.id else '  '}"
                f"**{entry['member'].display_name}** — "
                f"{entry['tickets']} ticket(s) ({pct:.1f}%)"
            )

        embed = discord.Embed(
            title="Raffle Result",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Item", value=item_name, inline=False)
        embed.add_field(name="Winner", value=winner.mention, inline=True)
        embed.add_field(name="Winner Tickets", value=str(winner_tickets), inline=True)
        embed.add_field(name="Session", value=f"`{session_id}`", inline=True)
        embed.add_field(
            name="Draw Odds",
            value="\n".join(odds_lines) or "—",
            inline=False,
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot, sheets: SheetsClient) -> None:
    await bot.add_cog(Loot(bot, sheets))
