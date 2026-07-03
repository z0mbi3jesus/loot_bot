"""Purchase request and approval cog."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from bot_utils import send_bot_message
from sheets import SheetsClient


def _is_officer(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.name == config.OFFICER_ROLE for r in interaction.user.roles)


class Purchases(commands.Cog):
    def __init__(self, bot: commands.Bot, sheets: SheetsClient) -> None:
        self.bot = bot
        self.sheets = sheets

    # ------------------------------------------------------------------
    # /request_purchase
    # ------------------------------------------------------------------

    @app_commands.command(
        name="request_purchase",
        description="Request a SHAFTcoin™ purchase and send it to officers for approval.",
    )
    @app_commands.describe(
        amount="The SHAFTcoin™ cost of the purchase.",
        description="Describe what you are requesting approval to buy.",
    )
    async def request_purchase(
        self,
        interaction: discord.Interaction,
        amount: int,
        description: str,
    ) -> None:
        await interaction.response.defer(ephemeral=False)

        if amount <= 0:
            await send_bot_message(
                interaction,
                content="Purchase amount must be a positive integer.",
                ephemeral=True,
            )
            return

        requester = interaction.user
        if not isinstance(requester, discord.Member):
            await send_bot_message(
                interaction,
                content="Could not identify your Discord member details.",
                ephemeral=True,
            )
            return

        request_id = self.sheets.create_purchase_request(
            requester_id=requester.id,
            requester_name=requester.display_name,
            amount=amount,
            description=description,
        )

        embed = discord.Embed(
            title="Purchase Request Submitted",
            color=discord.Color.green(),
        )
        embed.add_field(name="Request ID", value=f"`{request_id}`", inline=True)
        embed.add_field(name="Requester", value=requester.mention, inline=True)
        embed.add_field(name="Amount", value=str(amount), inline=True)
        embed.add_field(name="Description", value=description, inline=False)
        embed.set_footer(text="Officers can approve or deny this request with /approve_purchase or /deny_purchase.")

        await send_bot_message(interaction, embed=embed)

    # ------------------------------------------------------------------
    # /purchase_status
    # ------------------------------------------------------------------

    @app_commands.command(
        name="purchase_status",
        description="View the approval status of a purchase request.",
    )
    @app_commands.describe(request_id="The purchase request ID to inspect.")
    async def purchase_status(
        self,
        interaction: discord.Interaction,
        request_id: str,
    ) -> None:
        request = self.sheets.get_purchase_request(request_id)
        if request is None:
            await send_bot_message(
                interaction,
                content=f"Purchase request `{request_id}` was not found.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Purchase Request Status",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Request ID", value=f"`{request_id}`", inline=True)
        embed.add_field(name="Requester", value=f"<@{request['requester_id']}>", inline=True)
        embed.add_field(name="Amount", value=str(request["amount"]), inline=True)
        embed.add_field(name="Status", value=request["status"].capitalize(), inline=True)
        embed.add_field(name="Description", value=request["description"], inline=False)
        if request.get("approver_name"):
            embed.add_field(name="Approved By", value=request["approver_name"], inline=True)
        if request.get("reason"):
            embed.add_field(name="Reason", value=request["reason"], inline=False)
        embed.add_field(name="Created", value=request["created_at"], inline=True)
        embed.add_field(name="Updated", value=request["updated_at"], inline=True)

        await send_bot_message(interaction, embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # /pending_purchases
    # ------------------------------------------------------------------

    @app_commands.command(
        name="pending_purchases",
        description="List pending purchase requests for officers.",
    )
    async def pending_purchases(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if not _is_officer(interaction):
            await send_bot_message(
                interaction,
                content=f"Only members with the **{config.OFFICER_ROLE}** role can view pending purchases.",
                ephemeral=True,
            )
            return

        requests = self.sheets.get_purchase_requests(status="pending")
        if not requests:
            await send_bot_message(
                interaction,
                content="There are no pending purchase requests.",
                ephemeral=True,
            )
            return

        lines = [
            f"`{req['request_id']}` — <@{req['requester_id']}> — {req['amount']} coins — {req['description']}"
            for req in requests
        ]
        embed = discord.Embed(
            title="Pending Purchase Requests",
            description="\n".join(lines[:20]),
            color=discord.Color.gold(),
        )
        if len(lines) > 20:
            embed.set_footer(text=f"Showing the first 20 of {len(lines)} pending requests.")

        await send_bot_message(interaction, embed=embed)

    # ------------------------------------------------------------------
    # /approve_purchase
    # ------------------------------------------------------------------

    @app_commands.command(
        name="approve_purchase",
        description="Approve a pending purchase request and deduct SHAFTcoin™.",
    )
    @app_commands.describe(
        request_id="The purchase request ID to approve.",
        reason="Optional approval note.",
    )
    async def approve_purchase(
        self,
        interaction: discord.Interaction,
        request_id: str,
        reason: str = "Approved by officer",
    ) -> None:
        await interaction.response.defer(ephemeral=False)

        if not _is_officer(interaction):
            await send_bot_message(
                interaction,
                content=f"Only members with the **{config.OFFICER_ROLE}** role can approve purchases.",
                ephemeral=True,
            )
            return

        request = self.sheets.get_purchase_request(request_id)
        if request is None:
            await send_bot_message(
                interaction,
                content=f"Purchase request `{request_id}` was not found.",
                ephemeral=True,
            )
            return

        if request["status"] != "pending":
            await send_bot_message(
                interaction,
                content=f"Purchase request `{request_id}` is already {request['status']}.",
                ephemeral=True,
            )
            return

        balance = self.sheets.get_shaftcoin_balance(int(request["requester_id"]))
        if balance < int(request["amount"]):
            await send_bot_message(
                interaction,
                content=(
                    f"Requester <@{request['requester_id']}> only has {balance} coins, "
                    f"which is insufficient to approve this {request['amount']}-coin purchase."
                ),
                ephemeral=True,
            )
            return

        self.sheets.adjust_shaftcoin_balance(
            int(request["requester_id"]),
            request["requester_name"],
            -int(request["amount"]),
            "purchase",
            f"Approved purchase {request_id}",
            request_id,
        )
        self.sheets.update_purchase_request_status(
            request_id,
            "approved",
            approver_id=interaction.user.id if isinstance(interaction.user, discord.Member) else None,
            approver_name=(interaction.user.display_name if isinstance(interaction.user, discord.Member) else "Officer"),
            reason=reason,
        )

        embed = discord.Embed(
            title="Purchase Approved",
            color=discord.Color.green(),
        )
        embed.add_field(name="Request ID", value=f"`{request_id}`", inline=True)
        embed.add_field(name="Requester", value=f"<@{request['requester_id']}>", inline=True)
        embed.add_field(name="Amount", value=str(request["amount"]), inline=True)
        embed.add_field(name="Approver", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)

        await send_bot_message(interaction, embed=embed)

    # ------------------------------------------------------------------
    # /deny_purchase
    # ------------------------------------------------------------------

    @app_commands.command(
        name="deny_purchase",
        description="Deny a pending purchase request.",
    )
    @app_commands.describe(
        request_id="The purchase request ID to deny.",
        reason="Optional denial reason.",
    )
    async def deny_purchase(
        self,
        interaction: discord.Interaction,
        request_id: str,
        reason: str = "Denied by officer",
    ) -> None:
        await interaction.response.defer(ephemeral=False)

        if not _is_officer(interaction):
            await send_bot_message(
                interaction,
                content=f"Only members with the **{config.OFFICER_ROLE}** role can deny purchases.",
                ephemeral=True,
            )
            return

        request = self.sheets.get_purchase_request(request_id)
        if request is None:
            await send_bot_message(
                interaction,
                content=f"Purchase request `{request_id}` was not found.",
                ephemeral=True,
            )
            return

        if request["status"] != "pending":
            await send_bot_message(
                interaction,
                content=f"Purchase request `{request_id}` is already {request['status']}.",
                ephemeral=True,
            )
            return

        self.sheets.update_purchase_request_status(
            request_id,
            "denied",
            approver_id=interaction.user.id if isinstance(interaction.user, discord.Member) else None,
            approver_name=(interaction.user.display_name if isinstance(interaction.user, discord.Member) else "Officer"),
            reason=reason,
        )

        embed = discord.Embed(
            title="Purchase Denied",
            color=discord.Color.red(),
        )
        embed.add_field(name="Request ID", value=f"`{request_id}`", inline=True)
        embed.add_field(name="Requester", value=f"<@{request['requester_id']}>", inline=True)
        embed.add_field(name="Approver", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)

        await send_bot_message(interaction, embed=embed)


async def setup(bot: commands.Bot, sheets: SheetsClient) -> None:
    await bot.add_cog(Purchases(bot, sheets))
