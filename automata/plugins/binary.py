from discord import app_commands
from discord.ext import commands

from automata.utils import CommandContext, Plugin


class Binary(Plugin):
    """Encode text as binary."""

    @app_commands.describe(message="The text to encode.")
    @commands.hybrid_command(description="Encode text as binary bytes.")
    async def binary(self, ctx: CommandContext, message: str):
        """Encode text as binary bytes."""
        binary_string = ""

        for char in message:
            binary_string += format(ord(char), "b") + " "

        await ctx.send(binary_string)
