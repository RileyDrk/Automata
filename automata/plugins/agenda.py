import logging
import uuid
from datetime import datetime

from discord import app_commands
from discord.ext import commands

from automata.mongo import mongo
from automata.utils import CommandContext, Plugin, send_code_block_maybe_as_file

logger = logging.getLogger("Agenda")


class Agenda(Plugin):
    """Handles tracking agenda items, and exporting them as markdown"""

    async def send_agenda_text(self, ctx: CommandContext, variant: str | None):
        items = self.agenda_items.find({})

        text = "% MUN Computer Science Society\n% Meeting Agenda\n"
        text += f"% {datetime.now().strftime('%B %e, %Y')}\n"

        while await items.fetch_next:
            item = items.next_object()

            author_postfix = ""

            if variant != "clean":
                author_postfix = f" ({item['id']})"

            text += f'\n## {item["title"]} - {item["author"]}{author_postfix}\n{item["description"]}\n'

        await send_code_block_maybe_as_file(ctx, text)

    async def cog_load(self):
        self.agenda_items = mongo.automata.agenda_items

    @commands.hybrid_group(description="Manage the meeting agenda.")
    async def agenda(self, ctx: CommandContext):
        """Manage the meeting agenda."""
        pass

    @app_commands.describe(
        title="A short title for the agenda item.",
        description="Details for the agenda item.",
    )
    @agenda.command(description="Add an item to the meeting agenda.")
    @commands.has_permissions(manage_messages=True)
    async def add(self, ctx: CommandContext, title: str, description: str):
        """Add an item to the meeting agenda."""

        id = str(uuid.uuid4())[:8]

        item = {
            "id": id,
            "title": title,
            "description": description,
            "author": getattr(ctx.author, "nick", None) or ctx.author.display_name,
        }

        await self.agenda_items.insert_one(item)

        await ctx.send(f"Added item: {title} (`{id}`), with description: {description}")

    @app_commands.describe(variant="Use `clean` to omit item IDs from the export.")
    @agenda.command(description="View or export the current meeting agenda.")
    async def view(self, ctx: CommandContext, variant: str | None = None):
        """View or export the current meeting agenda."""
        await self.send_agenda_text(ctx, variant)

    @agenda.command(description="Export and then clear every agenda item.")
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx: CommandContext):
        """Export and then clear every agenda item."""
        await self.send_agenda_text(ctx, "clean")

        await self.agenda_items.delete_many({})

        await ctx.send("Cleared all agenda items")

    @app_commands.describe(id="The eight-character ID shown beside the agenda item.")
    @agenda.command(description="Remove an agenda item by its ID.")
    @commands.has_permissions(manage_messages=True)
    async def remove(self, ctx: CommandContext, id: str):
        """Remove an agenda item by its ID."""

        await self.agenda_items.delete_one({"id": id})

        await ctx.send(f"Removed agenda item `{id}`.")
