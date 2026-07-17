"""Email-based MUN student verification.

Configure the ``AUTOMATA_EMAIL_VERIFICATION_*`` settings before enabling this
plugin.  The plugin only accepts addresses in the ``@mun.ca`` domain and never
stores the one-time code itself.
"""

import asyncio
import hashlib
import hmac
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any

import discord
from discord.ext import commands
from pymongo.errors import DuplicateKeyError

from automata.config import config
from automata.mongo import mongo
from automata.utils import CommandContext, Plugin


class EmailVerification(Plugin):
    """Verify MUN students by emailing a one-time code to their @mun.ca address."""

    def _is_configured(self) -> bool:
        return bool(
            config.email_verification_secret
            and config.email_verification_smtp_host
            and config.email_verification_from_address
        )

    async def cog_load(self) -> None:
        self.verifications = mongo.automata.email_verifications
        await self.verifications.create_index("email", unique=True)
        await self.verifications.create_index("discord_id", unique=True)
        await self.verifications.create_index("expires_at", expireAfterSeconds=0)

    @staticmethod
    def _normalise_email(email: str) -> str | None:
        email = email.strip().casefold()
        local_part, separator, domain = email.rpartition("@")
        if not separator or not local_part or domain != "mun.ca":
            return None
        if any(character.isspace() for character in email):
            return None
        return email

    def _code_hash(self, email: str, code: str) -> str:
        message = f"{email}:{code}".encode()
        return hmac.new(
            config.email_verification_secret.encode(), message, hashlib.sha256
        ).hexdigest()

    @staticmethod
    def _is_expired(expires_at: object) -> bool:
        if not isinstance(expires_at, datetime):
            return True
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at <= datetime.now(timezone.utc)

    def _send_verification_email(self, email: str, code: str) -> None:
        message = EmailMessage()
        message["From"] = config.email_verification_from_address
        message["To"] = email
        message["Subject"] = "Your MUN Discord verification code"
        message.set_content(
            "Use this code in Discord to verify your MUN email address:\n\n"
            f"{code}\n\n"
            f"This code expires in {config.email_verification_code_ttl_minutes} minutes. "
            "If you did not request this code, you can ignore this email."
        )

        context = ssl.create_default_context()
        if config.email_verification_smtp_use_ssl:
            client: smtplib.SMTP | smtplib.SMTP_SSL = smtplib.SMTP_SSL(
                config.email_verification_smtp_host,
                config.email_verification_smtp_port,
                timeout=15,
                context=context,
            )
        else:
            client = smtplib.SMTP(
                config.email_verification_smtp_host,
                config.email_verification_smtp_port,
                timeout=15,
            )
        with client:
            if config.email_verification_smtp_starttls and not config.email_verification_smtp_use_ssl:
                client.starttls(context=context)
            if config.email_verification_smtp_username:
                client.login(
                    config.email_verification_smtp_username,
                    config.email_verification_smtp_password,
                )
            client.send_message(message)

    async def _primary_guild_member(
        self, ctx: CommandContext
    ) -> tuple[discord.Guild, discord.Member] | None:
        if ctx.guild is None or ctx.guild.id != config.primary_guild:
            await ctx.send("Email verification can only be completed in this server.")
            return None
        member = ctx.guild.get_member(ctx.author.id)
        if member is None:
            await ctx.send("I could not find your server membership. Please try again.")
            return None
        return ctx.guild, member

    @commands.group(invoke_without_command=True)
    async def emailverify(self, ctx: CommandContext) -> None:
        """Verify your MUN email address with `!emailverify start` and `!emailverify code`."""
        await ctx.send(
            "Use `!emailverify start your.name@mun.ca` to receive a code, then "
            "`!emailverify code 12345678` to receive the verified role."
        )

    @emailverify.command(name="start")
    @commands.cooldown(3, 3600, commands.BucketType.user)
    async def emailverify_start(self, ctx: CommandContext, email: str) -> None:
        """Send a verification code to a @mun.ca email address."""
        if not self._is_configured():
            await ctx.send("Email verification has not been configured by the server admins.")
            return
        if await self._primary_guild_member(ctx) is None:
            return

        email = self._normalise_email(email)
        if email is None:
            await ctx.send("Please provide a valid `@mun.ca` email address.")
            return

        now = datetime.now(timezone.utc)
        existing_email = await self.verifications.find_one({"email": email})
        if existing_email and not existing_email.get("verified_at") and self._is_expired(
            existing_email.get("expires_at")
        ):
            await self.verifications.delete_one({"_id": existing_email["_id"]})
            existing_email = None
        if existing_email and existing_email["discord_id"] != ctx.author.id:
            await ctx.send("That MUN email address is already associated with another Discord account.")
            return
        if existing_email and existing_email.get("verified_at"):
            await ctx.send("That email address is already verified for your account.")
            return

        code = f"{secrets.randbelow(100_000_000):08d}"
        code_hash = self._code_hash(email, code)
        expires_at = now + timedelta(minutes=config.email_verification_code_ttl_minutes)
        try:
            await self.verifications.update_one(
                {"discord_id": ctx.author.id},
                {
                    "$set": {
                        "email": email,
                        "code_hash": code_hash,
                        "expires_at": expires_at,
                        "requested_at": now,
                    },
                    "$unset": {"verified_at": ""},
                },
                upsert=True,
            )
        except DuplicateKeyError:
            await ctx.send("That MUN email address is already associated with another Discord account.")
            return

        try:
            await asyncio.to_thread(self._send_verification_email, email, code)
        except (OSError, smtplib.SMTPException):
            await self.verifications.delete_one(
                {"discord_id": ctx.author.id, "code_hash": code_hash}
            )
            await ctx.send("I could not send the verification email. Please try again later.")
            return

        await ctx.send(
            "A verification code has been sent to your MUN email. It expires in "
            f"{config.email_verification_code_ttl_minutes} minutes."
        )

    @emailverify.command(name="code")
    @commands.cooldown(5, 300, commands.BucketType.user)
    async def emailverify_code(self, ctx: CommandContext, code: str) -> None:
        """Confirm an emailed verification code and receive the verified role."""
        member_data = await self._primary_guild_member(ctx)
        if member_data is None:
            return
        guild, member = member_data

        verification: dict[str, Any] | None = await self.verifications.find_one(
            {"discord_id": ctx.author.id}
        )
        if verification is None:
            await ctx.send("Start verification first with `!emailverify start your.name@mun.ca`.")
            return
        if verification.get("verified_at"):
            await ctx.send("Your MUN email is already verified.")
            return

        expires_at = verification.get("expires_at")
        if self._is_expired(expires_at):
            await self.verifications.delete_one({"_id": verification["_id"]})
            await ctx.send("That code has expired. Please request a new one.")
            return
        expected_hash = self._code_hash(verification["email"], code.strip())
        if not hmac.compare_digest(verification.get("code_hash", ""), expected_hash):
            await ctx.send("That code is not valid. Please check it and try again.")
            return

        role = guild.get_role(config.verified_role)
        if role is None:
            await ctx.send("The verified role has not been configured by the server admins.")
            return
        try:
            await member.add_roles(role, reason="Verified with a MUN email address")
        except discord.Forbidden:
            await ctx.send("I do not have permission to grant the verified role. Please contact an admin.")
            return
        except discord.HTTPException:
            await ctx.send("I could not grant the verified role. Please try again later.")
            return

        await self.verifications.update_one(
            {"_id": verification["_id"]},
            {
                "$set": {"verified_at": datetime.now(timezone.utc)},
                "$unset": {"code_hash": "", "expires_at": ""},
            },
        )
        await ctx.send("Your MUN email has been verified and you have received the verified role!")
