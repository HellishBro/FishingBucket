from typing import Literal

from .generic import hook_command
from .utils import require_permissions
from ..backend import database as db
from ..backend.database import Database
from ..service import Context, Channel, Role, User, Embed


def setup():
    @hook_command("permissions set")
    async def _(context: Context, allow_list: list[Channel | Role | User] | Literal["community"], allow: bool | Literal["default"]):
        await require_permissions(context, lambda p: p.manage_guild)

        guild = db.Guild((await context.get_channel(context.message.channel_id)).guild_id, context.platform)
        allows = {
            True: "allow",
            False: "disallow",
            "default": "default"
        }[allow]

        if allow_list == "community":
            await Database.instance.set_guild_preferences(guild, allow not in ("allow", "default"), None)
            await context.reply("", [Embed(
                "Community Settings Changed!",
                f"Community default has been changed to {'allowing' if allow in ('allow', 'default') else 'disallowing'} proxying. Any previous or future channel-specific override will override this default. View them by using the `list allows` command."
            )])
            return

        mentions = []
        for thing in allow_list:
            id_type = -1
            if isinstance(thing, Channel):
                id_type = 0
            if isinstance(thing, Role):
                id_type = 1
            if isinstance(thing, User):
                id_type = 2
            mentions.append(f"{thing.mention}")

            await Database.instance.override_permission(thing.id, guild, allows, id_type)

        t = {
            "allow": "allowing proxying",
            "disallow": "disallowing proxying",
            "default": "default proxy settings"
        }[allows]
        await context.reply("", [Embed(
            "Community Settings Changed!",
            f"{len(allow_list)} changes has been made to be {t}: {', '.join(mentions)}."
        )])


    @hook_command("permissions reset")
    async def _(context: Context):
        await require_permissions(context, lambda p: p.manage_guild)
        guild = db.Guild((await context.get_channel(context.message.channel_id)).guild_id, context.platform)

        await Database.instance.remove_all_overrides(guild)
        await Database.instance.set_guild_preferences(guild, False, None)
        await context.reply("", [Embed(
            "Community Settings Changed!",
            f"All custom community proxy settings has been reset to allow proxying."
        )])


    @hook_command("permissions list")
    async def _(context: Context):
        guild = db.Guild((await context.get_channel(context.message.channel_id)).guild_id, context.platform)

        preferences = await Database.instance.get_guild_preferences(guild)
        guild_disallow = preferences[0]
        allow_list = []
        disallow_list = []

        for id_type in range(3):
            overrides = await Database.instance.get_guild_overrides(guild, id_type)
            for override, allow in overrides.items():
                lst = allow_list if allow == "allow" else disallow_list if allow == "disallow" else []
                if id_type == 0:
                    lst.append(f"<#{override}>")
                if id_type == 1:
                    lst.append(f"<@&{override}>")
                if id_type == 2:
                    lst.append(f"<@{override}>")

        allow_list = "\n".join("- " + l for l in allow_list) if allow_list else "- There are no overrides that explicitly allow proxies."
        disallow_list = "\n".join("- " + l for l in disallow_list) if disallow_list else "- There are no overrides that explicitly disallow proxies."

        await context.reply("", [Embed(
            "Community Settings",
            f"Community default is **{'disallow' if guild_disallow else 'allow'} proxying**.\n\nExplicitly **allowed** overrides:\n{allow_list}\n\nExplicitly **disallowed** overrides:\n{disallow_list}"
        )])


    @hook_command("log set")
    async def _(context: Context, channel: Channel | None):
        guild = db.Guild((await context.get_channel(context.message.channel_id)).guild_id, context.platform)

        if channel is None:
            await Database.instance.set_guild_preferences(guild, None, 0)
            await context.reply("", [Embed(
                "Community Settings Changed!",
                "Logging is now disabled for this community!"
            )])
        else:
            await Database.instance.set_guild_preferences(guild, None, channel.id)
            await context.reply("", [Embed(
                "Community Settings Changed!",
                f"Proxied messages will be logged to <#{channel.id}>."
            )])


    @hook_command("log view")
    async def _(context: Context):
        guild = db.Guild((await context.get_channel(context.message.channel_id)).guild_id, context.platform)
        preferences = await Database.instance.get_guild_preferences(guild)
        channel = preferences.logging_channel

        await context.reply("", [Embed(
            "Community Settings",
            f"The community logging channel is set to <#{channel}>." if channel else "There is no logging channel set in this community."
        )])

