import urllib.parse

from discord import app_commands
from discord.ext import commands

from automata.utils import CommandContext, Plugin


class LMGTFY(Plugin):
    """Create a LMGTFY link, for people who should have google'd first"""

    @app_commands.describe(search_terms="The search query to put in the link.")
    @commands.hybrid_command(description="Create a Let Me Google That For You link.")
    async def lmgtfy(self, ctx: CommandContext, *, search_terms: str):
        """Create a Let Me Google That For You link."""

        search_terms = urllib.parse.quote(search_terms)
        url = f"http://lmgtfy.com/?q={search_terms}"

        await ctx.send(url)
