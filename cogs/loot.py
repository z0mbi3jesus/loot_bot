"""Loot raffle cog — weighted random draw from session attendees."""

from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands

import config
from sheets import SheetsClient
from cogs.attendance import Attendance


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

    def _get_attendance_cog(self) -> Attendance | None:
        return self.bot.cogs.get("Attendance")  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # /raffle_loot
    # ------------------------------------------------------------------

    @app_commands.command(
        name="raffle_loot",
        description="Run a weighted raffle among session attendees for an item (Officer only).",
    )
    @app_commands.describe(
        item_name="Name of the item being raffled.",
    )
    async def raffle_loot(
        self,
        interaction: discord.Interaction,
        item_name: str,
    ) -> None:
        await interaction.response.defer(ephemeral=False)

        if not _is_officer(interaction):
            await interaction.followup.send(
                f"Only members with the **{config.OFFICER_ROLE}** role can run raffles.",
                ephemeral=True,
            )
            return

        attendance_cog = self._get_attendance_cog()
        session_id = (
            attendance_cog.get_active_session(interaction.guild_id)
            if attendance_cog
            else None
        )

        if session_id is None:
            await interaction.followup.send(
                "No active session. Start one with `/start_session` first.",
                ephemeral=True,
            )
            return

        attendee_ids = attendance_cog.get_attendee_ids(interaction.guild_id) if attendance_cog else []
        if not attendee_ids:
            await interaction.followup.send("No attendees recorded for this session.", ephemeral=True)
            return

        # Build weighted pool from live ticket counts
        pool: list[dict] = []
        for uid in attendee_ids:
            member = interaction.guild.get_member(uid)
            if member is None:
                continue
            record = self.sheets.get_tickets(uid)
            pool.append({
                "member": member,
                "tickets": record["tickets"] if record else 0,
            })

        if not pool:
            await interaction.followup.send("Could not resolve any attendees.", ephemeral=True)
            return

        result = _weighted_draw(pool)
        winner: discord.Member = result["member"]
        tickets_spent: int = result["tickets"]

        # Winner loses all their tickets (reset to 0)
        self.sheets.upsert_member(winner.id, winner.display_name, tickets_delta=-tickets_spent)
        self.sheets.log_loot(
            session_id=session_id,
            item_name=item_name,
            winner_id=winner.id,
            winner_name=winner.display_name,
            tickets_spent=tickets_spent,
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
            title="🎲 Raffle Result",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Item", value=item_name, inline=False)
        embed.add_field(name="Winner", value=winner.mention, inline=True)
        embed.add_field(name="Tickets Used", value=str(tickets_spent), inline=True)
        embed.add_field(name="Session", value=f"`{session_id}`", inline=True)
        embed.add_field(
            name="Draw Odds",
            value="\n".join(odds_lines) or "—",
            inline=False,
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot, sheets: SheetsClient) -> None:
    await bot.add_cog(Loot(bot, sheets))
