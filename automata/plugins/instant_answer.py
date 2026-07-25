import re

import httpx
from discord import app_commands
from discord.ext import commands

from automata.utils import CommandContext, Plugin


class InstantAnswer(Plugin):
    """Wrapper for Instant Answer API from DuckDuckGo"""

    @app_commands.describe(argument="What you want to look up.")
    @commands.hybrid_command(name="ia", description="Look up a DuckDuckGo instant answer.")
    async def ia(self, ctx: CommandContext, *, argument: str):
        """Look up a DuckDuckGo instant answer."""

        output_template = (
            "**{subject}**: *Brought to you by **DuckDuckGo** Instant Answer API*\n\n"
            "```{abstractText}```\n"
            "**Source:** <{abstractUrl}> @ {abstractSource}"
        )

        subject = re.sub("[^ 0-9a-zA-Z]+", "", argument)
        url_template = "https://api.duckduckgo.com/?q={query}&format=json"
        url = url_template.format(query=subject.replace(" ", "+"))
        data = httpx.get(url).json()

        output = (
            "Sorry, no Instant Answer found."
            if data["AbstractURL"] == ""
            else output_template.format(
                subject=subject,
                abstractText=data["AbstractText"],
                abstractUrl=data["AbstractURL"],
                abstractSource=data["AbstractSource"],
            ).replace("``````", "")
        )

        await ctx.send(output)
