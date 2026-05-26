import fluxer

from .utils import require_permission
from .. import response
from ..backend.config import Config
from ..backend.database import Database, Guild, Platform
from ..commands import register_command, register_group
from ..backend.models import alternative, one_or_more

def setup(bot: fluxer.Bot):
    register_group("guild", "Community Commands", f"Commands that changes how {Config.instance.name} functions in your community.")

    @register_command(
        [alternative("global", one_or_more(alternative(fluxer.Channel, fluxer.Role, fluxer.User))), alternative(bool, "allow", "disallow", "default")], bot,
        "allow proxy", """
    Changes if members can proxy.
    You must have the **Manage Community** permission to use this command.
    This will not override previous settings. To reset everything, use the `reset allows` command.
    The resolution order is always: community, channel, role, and finally user.
    """, 'allow proxy <channel(s) OR role(s) OR user(s) OR "global"> <allow? OR "default">',
        ['allow proxy #general false', 'allow proxy global allow',
         'allow proxy #roleplay-city @can-proxy default', 'allow proxy @proxy-muted false'], "guild")
    async def allow_proxy(message: fluxer.Message, allowlist: list[fluxer.Channel | fluxer.Role | fluxer.User] | str, allow: bool | str):
        if not await require_permission(message, 0x20, "Manage Community"): return
        guild = Guild(message.guild_id, Platform.Fluxer)

        allow = ("allow" if allow else "disallow") if isinstance(allow, bool) else allow
        if allowlist == "global":
            await Database.instance.set_guild_preferences(guild, allow not in ("allow", "default"), None)
            await response.respond(message, "", embeds=[fluxer.Embed(
                "Community Settings Changed!",
                f"Community default has been changed to {'allowing' if allow in ('allow', 'default') else 'disallowing'} proxying. Any previous or future channel-specific override will override this default. View them by using the `list allows` command."
            )])
        else:
            mentions = []
            for thing in allowlist:
                id_type = -1
                if isinstance(thing, fluxer.Channel):
                    id_type = 0
                    mentions.append(f"<#{thing.id}>")
                if isinstance(thing, fluxer.Role):
                    id_type = 1
                    mentions.append(f"<@&{thing.id}>")
                if isinstance(thing, fluxer.User):
                    id_type = 2
                    mentions.append(f"<@{thing.id}>")

                await Database.instance.override_permission(thing.id, Guild(message.guild_id, Platform.Fluxer), allow, id_type)

            t = {"allow": "allowing proxying", "disallow": "disallowing proxying", "default": "default proxy settings"}[allow]
            await response.respond(message, "", embeds=[fluxer.Embed(
                "Community Settings Changed!",
                f"{len(allowlist)} changes has been made to {t}: {', '.join(mentions)}."
            )])

    @register_command([], bot, "reset allows", """
    Reset all proxying settings of this community.
    You must have the **Manage Community** permission to use this command.
    This will allow proxying everywhere in the community.
    This will remove all role, channel, and user overrides.
    """, "reset allows", ["reset allows"], "guild")
    async def reset_allows(message: fluxer.Message):
        if not await require_permission(message, 0x20, "Manage Community"): return
        guild = Guild(message.guild_id, Platform.Fluxer)

        await Database.instance.remove_all_overrides(guild)
        await Database.instance.set_guild_preferences(guild, False, None)
        await response.respond(message, "", embeds=[fluxer.Embed(
            "Community Settings Changed!",
            f"All custom community proxy settings has been reset to allow proxying."
        )])

    @register_command([], bot, "list allows", """
    See a list of places where proxying is allowed or disallowed.
    You *do not* need the Manage Community permission to use this command.
    """, "list allows", ["list allows"], "guild")
    async def list_allows(message: fluxer.Message):
        guild = Guild(message.guild_id, Platform.Fluxer)
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

        await response.respond(message, "", embeds=[fluxer.Embed(
            "Community Settings",
            f"Community default is **{'disallow' if guild_disallow else 'allow'} proxying**.\n\nExplicitly **allowed** overrides:\n{allow_list}\n\nExplicitly **disallowed** overrides:\n{disallow_list}"
        )])

    @register_command([alternative("clear", fluxer.Channel)], bot, "logging channel", """
    Sets the logging channel for each proxy message.
    If `channel` is set to "clear", then no logging will happen.
    """, 'logging channel <channel OR "clear">', ["logging channel clear", "logging channel #logging"], "guild")
    async def logging_channel(message: fluxer.Message, channel: str | fluxer.Channel):
        guild = Guild(message.guild_id, Platform.Fluxer)
        if channel == "clear":
            await Database.instance.set_guild_preferences(guild, None, 0)
            await response.respond(message, "", embeds=[fluxer.Embed(
                "Community Settings Changed!",
                "Logging is now disabled for this community!"
            )])
        else:
            await Database.instance.set_guild_preferences(guild, None, channel.id)
            await response.respond(message, "", embeds=[fluxer.Embed(
                "Community Settings Changed!",
                f"Proxied messages will be logged to <#{channel.id}>."
            )])