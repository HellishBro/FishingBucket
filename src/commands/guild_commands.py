import fluxer

from .utils import require_permission
from .. import response
from ..backend.config import Config
from ..backend.database import Database
from ..commands import register_command, register_group
from ..backend.models import alternative, one_or_more

def setup(bot: fluxer.Bot):
    register_group("guild", "Community Commands", f"Commands that changes how {Config.instance.name} functions in your community.")

    @register_command(
        [alternative("all", one_or_more(fluxer.Channel)), alternative(bool, "allow", "disallow", "default")], bot,
        "allow channels", """
    Changes if members can proxy in some channels.
    You must have the **Manage Community** permission to use this command.
    This will not override previous settings. To reset everything, use the `reset allows` command.
    Users will not be able to use proxy in channels explicitly disallowed.
    """, 'allow channels <channel(s) OR "all"> <allow? OR "default">',
        ['allow channels #general false', 'allow channels all allow',
         'allow channels #roleplay-city #roleplay-beach default'], "guild")
    async def allow_channels(message: fluxer.Message, allowlist: list[fluxer.Channel] | str, allow: bool | str):
        if not await require_permission(message, 0x20, "Manage Community"): return

        allow = ("allow" if allow else "disallow") if isinstance(allow, bool) else allow
        if allowlist == "all":
            await Database.instance.set_guild_preferences(message.guild_id, allow not in ("allow", "default"), None)
            await response.respond(message, "", embeds=[fluxer.Embed(
                "Community Settings Changed!",
                f"Community default has been changed to {'allowing' if allow in ('allow', 'default') else 'disallowing'} proxying. Any previous or future channel-specific override will override this default. View them by using the `list allows` command."
            )])
        else:
            for channel in allowlist:
                await Database.instance.override_channel(channel.id, channel.guild_id, allow)

            t = {"allow": "allowing proxying", "disallow": "disallowing proxying", "default": "default proxy settings"}[
                allow]
            await response.respond(message, "", embeds=[fluxer.Embed(
                "Community Settings Changed!",
                f"{len(allowlist)} channel{'s' if len(allowlist) != 1 else ''} has been changed to {t}: {', '.join(('<#' + str(c.id) + '>') for c in allowlist)}."
            )])

    @register_command([], bot, "reset allows", """
    Reset all proxying settings of this community.
    You must have the **Manage Community** permission to use this command.
    This will allow proxying everywhere in the community.
    """, "reset allows", ["reset allows"], "guild")
    async def reset_allows(message: fluxer.Message):
        if not await require_permission(message, 0x20, "Manage Community"): return

        await Database.instance.remove_all_channel_overrides(int(message.guild_id))
        await Database.instance.set_guild_preferences(message.guild_id, False, None)
        await response.respond(message, "", embeds=[fluxer.Embed(
            "Community Settings Changed!",
            f"All custom community proxy settings has been reset to allow proxying."
        )])

    @register_command([], bot, "list allows", """
    See a list of places where proxying is allowed or disallowed.
    You *do not* need the Manage Community permission to use this command.
    """, "list allows", ["list allows"], "guild")
    async def list_allows(message: fluxer.Message):
        preferences = await Database.instance.get_guild_preferences(message.guild_id)
        guild_disallow = preferences[0]
        channel_overrides = await Database.instance.get_guild_channel_overrides(message.guild_id)
        explicit_allows = [k for k, v in channel_overrides.items() if v == "allow"]
        explicit_disallows = [k for k, v in channel_overrides.items() if v == "disallow"]

        allow_list = '\n'.join(('- <#' + str(k) + '> (`' + str(k) + '`)') for k in
                               explicit_allows) or "- There are no channels that explicitly allow proxies."
        disallow_list = '\n'.join(('- <#' + str(k) + '> (`' + str(k) + '`)') for k in
                                  explicit_disallows) or "- There are no channels that explicitly disallow proxies."

        await response.respond(message, "", embeds=[fluxer.Embed(
            "Community Settings",
            f"Community default is **{'disallow' if guild_disallow else 'allow'} proxying**.\n\nExplicitly **allowed** channels:\n{allow_list}\n\nExplicitly **disallowed** channels:\n{disallow_list}"
        )])

    @register_command([alternative("clear", fluxer.Channel)], bot, "logging channel", """
    Sets the logging channel for each proxy message.
    If `channel` is set to "clear", then no logging will happen.
    """, 'logging channel <channel OR "clear">', ["logging channel clear", "logging channel #logging"], "guild")
    async def logging_channel(message: fluxer.Message, channel: str | fluxer.Channel):
        if channel == "clear":
            await Database.instance.set_guild_preferences(message.guild_id, None, 0)
            await response.respond(message, "", embeds=[fluxer.Embed(
                "Community Settings Changed!",
                "Logging is now disabled for this community!"
            )])
        else:
            await Database.instance.set_guild_preferences(message.guild_id, None, channel.id)
            await response.respond(message, "", embeds=[fluxer.Embed(
                "Community Settings Changed!",
                f"Proxied messages will be logged to <#{channel.id}>."
            )])