import time
import fluxer
from textdistance import damerau_levenshtein

from .utils import proxy_username, paged_proxy_list, ensure_own_proxy, get_proxies_text, require_reply, valid_template, \
    example_trigger_text
from .. import response
from ..backend.database import Database
from ..commands import register_command, register_group
from ..interaction import Interactions
from ..interactions_impl import show_proxy_info
from ..backend.models import optional_type, Proxy, alternative
from ..send_proxy import reproxy as proxy_reproxy
from ..backend.utils import get_guild_id_from_channel, normalize_emojis


def setup(bot: fluxer.Bot):
    register_group("proxy", "Proxy Commands", "Commands related to creating, getting, and using proxies.")

    @register_command([proxy_username, str], bot, "register", """
    Registers a proxy to be used.
    The trigger is a string that contains `{}` somewhere.
    Proxy avatar can be set by attaching an image to the message.
    """, "register <name> <trigger>",['register Example example says {}', 'register "Long name" ln: {}'], "proxy")
    async def register(message: fluxer.Message, name: str, trigger: str):
        if not await valid_template(message, "Trigger", trigger): return

        name = normalize_emojis(name)

        if not message.attachments:
            avatar_url = Proxy.random_avatar()
        else:
            avatar_url = message.attachments[0].url

        new_proxy = await Database.instance.put_proxy(Proxy(None, name, "", avatar_url, [trigger], int(message.author.id), 0, time.time(), None, ""))
        hex_id = str(hex(new_proxy.id))[2:].lower()
        embed = fluxer.Embed(
            f"{name} (`{hex_id}`)",
            f"Proxy **{name}** registered with an ID of `{hex_id}`!\nSay hello with it by typing `{example_trigger_text(trigger)}`!"
        )
        embed.set_thumbnail(url=avatar_url)
        await response.respond(message, "", [embed])


    @register_command([optional_type(fluxer.User), optional_type(int)], bot, "list", """
    Lists your registered proxies.
    If `user` is provided, it will display the proxies of that user, and if not provided, it will default to your proxies.
    If `page` is provided, it will display the proxies on that page number. Defaults to 1.
    """, "list [user] [page]", ["list", "list 4", "list @Gordon", "list @Phil 43"], "proxy")
    async def list_(message: fluxer.Message, user: fluxer.User | None, page: int | None):
        uid = user.id if user else message.author.id
        name = user.display_name if user else message.author.display_name
        if (await Database.instance.get_user_preferences(uid)).private_list and uid != message.author.id:
            await response.respond(message, "That user have a private proxy list!")
            return

        detailed = False
        if (await get_guild_id_from_channel(bot, message.channel_id)) is None:
            detailed = True

        await paged_proxy_list(
            message,
            await Database.instance.get_user_proxies(uid),
            f"Registered Proxies of {name}",
            page,
            detailed
        )


    @register_command([str, optional_type(int)], bot, "find", """
    Finds all your proxies matching a name.
    If `page` is provided, it will display the proxies on that page number. Defaults to 1.
    The `name` is searched via fuzzy text searching. It will match if any portion of the name is matched, regardless of capitalization.
    """, "find <name> [page]", ['find Example', 'find "Usain Bolt" 2'], "proxy")
    async def find(message: fluxer.Message, name: str, page: int | None):
        detailed = False
        if (await get_guild_id_from_channel(bot, message.channel_id)) is None:
            detailed = True

        name = normalize_emojis(name)

        proxies = await Database.instance.get_user_proxies(message.author.id)
        proxies = [proxy for proxy in proxies if (name.lower() in proxy.name.lower()) or (name.lower() in (proxy.nickname or "").lower())]
        distances = {i: min(damerau_levenshtein(name.lower(), valid_proxy.name.lower()), damerau_levenshtein(name.lower(), (valid_proxy.nickname or valid_proxy.name).lower())) for i, valid_proxy in enumerate(proxies)}
        distances = {k: v for k, v in distances.items() if v <= 5}
        sorted_distances = dict(sorted(distances.items(), key=lambda kv: kv[1]))
        sorted_indices = sorted_distances.keys()
        sorted_proxies = []
        for index in sorted_indices:
            sorted_proxies.append(proxies[index])

        await paged_proxy_list(
            message,
            sorted_proxies,
            f"Proxy Search: **{name}**",
            page,
            detailed
        )


    @register_command([str], bot, "reproxy", """
    Changes the proxy of your message in this channel.
    This will delete and resend your previous proxied message in this channel.
    Alternatively, reply to a message to reproxy that message instead.
    """, "reproxy <new proxy>", ["reproxy 69ed73"], "proxy")
    async def reproxy(message: fluxer.Message, new_id: str):
        channel_id = message.channel_id
        if message.referenced_message:
            message_id = message.referenced_message.id
            proxy_id = await Database.instance.get_proxy_id(message_id, channel_id)
            old_proxy = await ensure_own_proxy(message, proxy_id)
            if not old_proxy: return
        else:
            message_id = await Database.instance.get_latest_proxy_message_from_user(channel_id, message.author.id)
            if not message_id:
                m = await response.respond(message, "There are no proxied messages from you in this channel! This message will expire in 15 seconds.")
                if await Interactions.instance.wait_claim_after(15, m.id, m.author.id):
                    await response.delete_message(m)
                    await message.delete()
                return
            proxy_id = await Database.instance.get_proxy_id(message_id, channel_id)
            old_proxy = await Database.instance.get_proxy(proxy_id)

        new_proxy = await ensure_own_proxy(message, new_id)
        if not new_proxy: return
        parent = await bot.fetch_message(str(channel_id), str(message_id))
        await message.delete()
        await proxy_reproxy(parent, bot, old_proxy, new_proxy)

    @register_command([alternative(bool, str)], bot, "autoproxy", """
    Automatically proxies your messages.
    Autoproxy set to `true` or `latch` will proxy your messages as your last used proxy.
    If it is an ID, all messages will be sent as that proxy.
    You can still use proxies normally. Any explicit proxy message will override the autoproxy for that message only.
    """, 'autoproxy <"latch" OR enabled OR proxy>', ["autoproxy latch", "autoproxy off", "autoproxy 69ed73"], "proxy")
    async def autoproxy(message: fluxer.Message, setting: str | bool):
        if setting in ("latch", "enable", "enabled"):
            setting = True
        elif setting in ("disable", "disabled"):
            setting = False
        if setting is True:
            await Database.instance.set_user_preferences(message.author.id, autoproxy=True, autoproxy_id=-1)
            await response.respond(message, "Autoproxy has been set to latch mode!")
        elif setting is False:
            await Database.instance.set_user_preferences(message.author.id, autoproxy=False)
            await response.respond(message, "Autoproxy has been turned off.")
        else:
            if not (proxy := await ensure_own_proxy(message, setting)):
                return
            await Database.instance.set_user_preferences(message.author.id, autoproxy=True, autoproxy_id=proxy.id)
            await response.respond(message, f"Autoproxying as **{proxy.name}**.")


    @register_command([str], bot, "info", """
    Shows you information about a proxy.
    This proxy has to be owned by you.
    """, "info <proxy>", ["info 69ed73"], "proxy")
    async def info(message: fluxer.Message, id_: str):
        proxy = await ensure_own_proxy(message, id_)
        if not proxy: return

        detailed = False
        if (await get_guild_id_from_channel(bot, message.channel_id)) is None:
            detailed = True

        embed = fluxer.Embed(
            f"{proxy.name}",
            get_proxies_text([proxy], await Database.instance.get_user_preferences(message.author.id), detailed)
        )
        embed.set_image(url=proxy.avatar_url)
        await response.respond(message, "", [embed])


    @register_command([], bot, "who", """
    Shows you information about a proxy message.
    This requires the command to be a reply to a message sent by a proxy.
    Alternatively, react to the message with a :question:.
    """, "who", ["who"], "proxy")
    async def who(message: fluxer.Message):
        if not (parent := await require_reply(message)): return
        if embed := await show_proxy_info(bot, parent):
            await message.author.send("", embeds=[embed])
            await message.delete()
        else:
            m = await response.respond(message, "That message is not a proxied message! This message will expire in 15 seconds.")
            if await Interactions.instance.wait_claim_after(15, m.id, m.author.id):
                await response.delete_message(m)
                await message.delete()


    @register_command([], bot, "delete", """
    Deletes a proxy message.
    This require the command to be a reply to a message sent by a proxy **that you own**.
    Alternatively, react to the message with a :x:.
    """, "delete", ["delete"], "proxy")
    async def delete(message: fluxer.Message):
        if not (parent := await require_reply(message)): return
        proxy_id = await Database.instance.get_proxy_id(parent.id, parent.channel_id)
        if proxy_id:
            proxy = await Database.instance.get_proxy(proxy_id)
            if proxy.owner == message.author.id:
                await Database.instance.delete_link_message(parent.id, parent.channel_id)
                await parent.delete()
                await message.delete()
                return
            m = await response.respond(message, "You do not own this proxy! This message will expire in 15 seconds.")
            if await Interactions.instance.wait_claim_after(15, m.id, m.author.id):
                await response.delete_message(m)
                await message.delete()
            return
        m = await response.respond(message, "That message is not a proxied message! This message will expire in 15 seconds.")
        if await Interactions.instance.wait_claim_after(15, m.id, m.author.id):
            await response.delete_message(m)
            await message.delete()


    '''
    @register_command([str], bot, "edit", """
    Edits a proxy message.
    This require the command to be a reply to a message sent by a proxy **that you own**.
    """, "edit <message>", ["edit We grew apart..."], "proxy")
    async def edit(message: fluxer.Message, new: str):
        if not (parent := await require_reply(message)): return
        proxy_id = await Database.instance.get_proxy_id(parent.id, parent.channel_id)
        if proxy_id:
            proxy = await Database.instance.get_proxy(proxy_id)
            if proxy.owner == message.author.id:
                webhook_id = await Database.instance.get_channel_webhook(parent.channel_id)
                if webhook_id:
                    webhook = await bot.fetch_webhook(str(webhook_id))
                    await edit_webhook(webhook, bot, message, new)
                    await message.delete()
                    return
            m = await response.respond(message, "You do not own this proxy! This message will expire in 15 seconds.")
            if await interactions.wait_claim_after(15, m.id):
                await response.delete_message(m)
                await message.delete()
            return
        m = await response.respond(message, "That message is not a proxied message! This message will expire in 15 seconds.")
        if await interactions.wait_claim_after(15, m.id):
            await response.delete_message(m)
            await message.delete()
    '''