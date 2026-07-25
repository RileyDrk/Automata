import discord
import httpx
from discord import app_commands
from discord.ext import commands

from automata.utils import CommandContext, Plugin

API_BASE = "http://numbersapi.com/"


class NumberFacts(Plugin):
    """Numbers have a secret facts, check them out!"""

    @staticmethod
    async def fetch(api_path: str) -> httpx.Response:
        async with httpx.AsyncClient() as client:
            return await client.get(f"{API_BASE}{api_path}")

    async def message_embed(self, fact: str, number: str) -> discord.Embed:
        embed = discord.Embed(colour=discord.Colour.random())
        embed.add_field(name=f"A fact about number {number}", value=fact)
        embed.set_author(name="NFact")

        return embed

    @app_commands.describe(number="A number to learn about, or leave blank for a random fact.")
    @commands.hybrid_command(name="numberfact", description="Get a fact about a number.")
    async def numberfact(self, ctx: CommandContext, number: str = "random"):
        """Get a fact about a number, or a random fact."""

        res = await self.fetch(number)
        fact = res.text

        nbr = fact.split(" ")[0]

        embed = await self.message_embed(fact, nbr)

        await ctx.send(embed=embed)

    @app_commands.describe(year="A year to learn about, or leave blank for a random fact.")
    @commands.hybrid_command(description="Get a historical fact about a year.")
    async def yearfact(self, ctx: CommandContext, year: str = "random"):
        """Get a historical fact about a year."""

        res = await self.fetch(f"{year}/year")
        fact = res.text

        nbr = fact.split(" ")[0]

        embed = await self.message_embed(fact, nbr)

        await ctx.send(embed=embed)

    @app_commands.describe(
        day="Day of the month (1-31). Leave both date options blank for random.",
        month="Month number (1-12). Leave both date options blank for random.",
    )
    @commands.hybrid_command(description="Get a fact about a calendar date.")
    async def datefact(
        self, ctx: CommandContext, day: int | None = None, month: int | None = None
    ):
        """Get a fact about a date, or a random date when both options are blank."""
        if (day is None) != (month is None):
            await ctx.send("Please provide both a day and a month, or leave both blank for a random date.")
            return
        if day is not None and not 1 <= day <= 31:
            await ctx.send("The day must be between 1 and 31.")
            return
        if month is not None and not 1 <= month <= 12:
            await ctx.send("The month must be between 1 and 12.")
            return

        res = await self.fetch(f"{month}/{day}/date" if day is not None else "random/date")

        fact = res.text

        nbr = " ".join(fact.split(" ")[0:2])
        embed = await self.message_embed(fact, nbr)

        await ctx.send(embed=embed)

    @app_commands.describe(number="A number to learn a mathematical fact about, or leave blank for random.")
    @commands.hybrid_command(description="Get a mathematical fact about a number.")
    async def mathfact(self, ctx: CommandContext, number: str = "random"):
        """Get a mathematical fact about a number."""

        res = await self.fetch(f"{number}/math")
        fact = res.text

        nbr = fact.split(" ")[0]

        embed = await self.message_embed(fact, nbr)

        await ctx.send(embed=embed)
