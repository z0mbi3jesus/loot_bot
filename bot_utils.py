from __future__ import annotations

import discord
from discord import Interaction

import config


def _get_bot_channel(interaction: Interaction) -> discord.TextChannel | None:
    if config.BOT_CHANNEL_ID is None or interaction.guild is None:
        return None

    channel = interaction.guild.get_channel(config.BOT_CHANNEL_ID)
    return channel if isinstance(channel, discord.TextChannel) else None


async def send_bot_message(
    interaction: Interaction,
    content: str | None = None,
    embed: discord.Embed | None = None,
    ephemeral: bool = False,
) -> None:
    if content is None and embed is None:
        raise ValueError("send_bot_message requires content or embed.")

    if ephemeral:
        if not interaction.response.is_done():
            await interaction.response.send_message(content=content, embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(content=content, embed=embed, ephemeral=True)
        return

    bot_channel = _get_bot_channel(interaction)
    if bot_channel is None:
        if not interaction.response.is_done():
            await interaction.response.send_message(content=content, embed=embed)
        else:
            await interaction.followup.send(content=content, embed=embed)
        return

    acknowledgement = f"Posted to <#{config.BOT_CHANNEL_ID}>."
    if not interaction.response.is_done():
        await interaction.response.send_message(acknowledgement, ephemeral=True)
    else:
        await interaction.followup.send(acknowledgement, ephemeral=True)

    await bot_channel.send(content=content, embed=embed)
