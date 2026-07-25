import logging
from typing import cast

import discord
from discord import app_commands
from discord.ext import commands

import automata.plugins as plugins
from automata.config import config
from automata.utils import CommandContext, CustomHelp

intents = discord.Intents.default()
intents.message_content = True
intents.members = config.member_intents_enabled


class Automata(commands.Bot):
    async def setup_hook(self) -> None:
        for plugin in plugins.enabled_plugins:
            await self.add_cog(plugin(self))

        # Guild command syncs are available immediately, unlike global commands,
        # which can take up to an hour to propagate.
        guild = discord.Object(id=config.primary_guild)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)


bot = Automata(
    command_prefix="!",
    description="A custom, multi-purpose moderation bot for the MUN Computer Science Society Discord server.",
    intents=intents,
    help_command=CustomHelp(),
)

logger = logging.getLogger(__name__)


@bot.event
async def on_message(message: discord.Message):
    if isinstance(message.channel, discord.DMChannel):
        name = message.author.name
    else:
        channel = cast(discord.TextChannel, message.channel)
        name = channel.name

    logger.info(f"[{name}] {message.author.name}: {message.content}")

    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx: CommandContext, error: commands.CommandError) -> None:
    """Give prefix-command users an actionable error instead of a traceback."""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("I don't recognize that command. Use Discord's `/` command picker to browse available commands.")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        command = ctx.command.qualified_name if ctx.command else "that command"
        await ctx.send(f"`/{command}` needs a `{error.param.name}` option. Run it again and fill in the prompted option.")
        return
    if isinstance(error, (commands.BadArgument, commands.BadUnionArgument)):
        await ctx.send("One of those options isn't valid. Please check the option format and try again.")
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use that command.")
        return
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send("That command can only be used in the server.")
        return
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Please try that again in {error.retry_after:.0f} seconds.")
        return

    logger.exception("Unhandled command error", exc_info=error)
    await ctx.send("Something went wrong while running that command. Please try again shortly.")


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    """Return concise, private guidance when a slash command cannot be run."""
    if isinstance(error, app_commands.MissingPermissions):
        message = "You don't have permission to use that command."
    elif isinstance(error, app_commands.NoPrivateMessage):
        message = "That command can only be used in the server."
    elif isinstance(error, app_commands.CommandOnCooldown):
        message = f"Please try that again in {error.retry_after:.0f} seconds."
    elif isinstance(error, app_commands.TransformerError):
        message = "One of those options isn't valid. Please check it and try again."
    else:
        logger.exception("Unhandled app command error", exc_info=error)
        message = "I couldn't run that command. Check its options and try again."

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


__all__ = ["bot"]
