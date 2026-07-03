"""Loot raffle cog — weighted random draw from session attendees."""

from __future__ import annotations

import random

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
            await send_bot_message(
                interaction,
                content=f"Only members with the **{config.OFFICER_ROLE}** role can run raffles.",
                ephemeral=True,
            )
            return

        session = self.sheets.get_session(session_id)
        if session is None:
            await send_bot_message(
                interaction, content=f"Session `{session_id}` was not found.", ephemeral=True
            )
            return

        ticket_records = self.sheets.get_session_ticket_records(session_id)
        if not ticket_records:
            await send_bot_message(
                interaction, content=f"No ticket records found for session `{session_id}`.", ephemeral=True
            )
            return

        # Build weighted pool from members who have at least 1 ticket in this session.
        pool: list[dict] = []
        for record in ticket_records:
            tickets = int(record.get("tickets", 0))
            if tickets < 1:
                continue

            member = interaction.guild.get_member(int(record["discord_id"]))
            if member is None:
                continue
            pool.append({
                "member": member,
                "tickets": tickets,
            })

        if not pool:
            await send_bot_message(
                interaction,
                content="No eligible members with at least 1 ticket were found in this server.",
                ephemeral=True,
            )
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
        await send_bot_message(interaction, embed=embed)


async def setup(bot: commands.Bot, sheets: SheetsClient) -> None:
    await bot.add_cog(Loot(bot, sheets))
