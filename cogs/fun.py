"""Standalone fun commands cog (not tied to sessions or tickets)."""

from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands


class Fun(commands.Cog):
    @app_commands.command(
        name="coin_flip",
        description="Flip a coin.",
    )
    async def coin_flip(self, interaction: discord.Interaction) -> None:
        result = random.choice(("Heads", "Tails"))

        embed = discord.Embed(
            title="Coin Flip",
            description=f"Result: **{result}**",
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="roll_d20",
        description="Roll a 20-sided die.",
    )
    async def roll_d20(self, interaction: discord.Interaction) -> None:
        roll = random.randint(1, 20)

        embed = discord.Embed(
            title="D20 Roll",
            description=f"You rolled: **{roll}**",
            color=discord.Color.teal(),
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fun())