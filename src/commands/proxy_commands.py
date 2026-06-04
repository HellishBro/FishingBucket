from datetime import datetime, timedelta
from typing import Literal

from textdistance import damerau_levenshtein as edit_distance

from .generic import hook_command
from .specific import get_uid
from .utils import example_trigger_text, paged_proxy_list, get_proxies_text
from ..backend.database import Database, MessageLink
from ..backend import database as db
from ..backend.models import Proxy
from ..backend.template_utils import Template
from ..backend.utils import normalize_emojis
from ..send_proxy import reproxy
from ..service import Context, Embed, Webhook


def setup():
    @hook_command("register")
    async def _(context: Context, name: str, trigger: Template):
        name = normalize_emojis(name)

        if not context.message.attachments:
            avatar_url = Proxy.random_avatar()
        else:
            avatar_url = context.message.attachments[0].url

        new_proxy = await Database.instance.put_proxy(
            Proxy(
                None,
                name,
                "",
                avatar_url,
                [trigger.string],
                await get_uid(context, True),
                0,
                datetime.now().timestamp(),
                None,
                "",
                {},
                None
            )
        )

        embed = Embed(
            f"{name} (`{new_proxy.id}`)",
            f"Proxy **{name}** is registered with an ID of `{new_proxy.id}`!\nSay hello with it by typing `{example_trigger_text(trigger)}`",
            thumbnail_url=avatar_url
        )
        await context.reply("", [embed])


    @hook_command("list")
    async def _(context: Context, page: int, detailed: bool):
        uid = await get_uid(context)

        await paged_proxy_list(
            context,
            await Database.instance.get_user_proxies(uid),
            f"Registered Proxies of {context.author.display_name}",
            page,
            context.channel.dm or detailed
        )


    @hook_command("find")
    async def _(context: Context, name: str):
        owner = await get_uid(context)

        norm_name = normalize_emojis(name)
        user_proxies = await Database.instance.get_user_proxies(owner)

        errors = []

        distances = {
            i: min(
                edit_distance(
                    norm_name.lower(), candidate.name.lower()
                ),
                edit_distance(
                    norm_name.lower(), (candidate.nickname or candidate.name).lower()
                )
            )
            for i, candidate in enumerate(user_proxies)
        }
        sorted_distances = dict(sorted(distances.items(), key=lambda kv: kv[1]))

        minimum_distance = min(distances.items(), key=lambda kv: kv[1])
        if minimum_distance[1] > 5:
            errors.append("- No name is close enough to the search term.")
        if [*distances.values()].count(minimum_distance[1]) > 1:
            errors.append("- There are two or more proxies with the same degree of similarity in name.")

        additional_embeds = []
        if errors:
            additional_embeds.append(Embed(
                "Errors",
                "\n".join(errors)
            ))

        await paged_proxy_list(
            context,
            [user_proxies[i] for i in sorted_distances],
            f"Proxy Search: **{name}**",
            0,
            context.channel.dm,
            additional_embeds
        )


    @hook_command("info")
    async def _(context: Context, proxy: Proxy, detailed: bool = False):
        uid = await get_uid(context)

        detailed = context.channel.dm or detailed

        await context.reply("", [Embed(
            proxy.name,
            get_proxies_text(
                [proxy],
                await Database.instance.get_user_preferences(uid),
                detailed
            )[0],
            thumbnail_url=proxy.effective_avatar
        )])


    @hook_command("reproxy")
    async def _(context: Context, proxy: Proxy):
        owner = await get_uid(context)

        if ref := await context.message.get_reference():
            message_id = ref.id
            message = ref
        else:
            message_id = await Database.instance.get_latest_proxy_message_from_user(context.channel.id, owner, context.platform)
            if (message := await context.channel.get_message(message_id)) is None or not message_id:
                await context.reply("Error: there are no previous proxied messages from you in this channel!")
                return

        message_link: MessageLink = await Database.instance.get_message_link(message_id, context.channel.id)
        proxy_id = message_link.proxy_id
        old_proxy = await Database.instance.get_proxy(proxy_id)

        if old_proxy.owner != owner:
            await context.reply("Error: you do not own the original proxy!")
            return

        await context.message.delete()
        await reproxy(message.context, old_proxy, proxy)


    @hook_command("autoproxy")
    async def _(context: Context, setting: Proxy | Literal["latch"] | bool, mode: Literal["global"] | Literal["community"] | None, expires: timedelta | Literal["never"]):
        if setting == "latch":
            setting = True

        if expires == "never":
            expiration = None
        else:
            expiration = expires.total_seconds()

        if mode == "global" or mode is None:
            guild = db.Guild(0, context.platform)
            postfix = "globally"
        else:
            guild = db.Guild(context.guild.id, context.platform)
            postfix = "in this community"

        uid = await get_uid(context)

        if setting is True:
            await Database.instance.set_autoproxy_preference(uid, guild, None, expiration)
            await context.reply(f"Autoproxy has been set to latch mode {postfix}.")
        elif setting is False:
            if mode is None:
                await Database.instance.remove_all_autoproxy_preference(uid)
                await context.reply("Autoproxy has been turned off for everything.")
                return

            await Database.instance.remove_autoproxy_preference(uid, guild)
            await context.reply(f"Autoproxy has been turned off {postfix}.")
        else:
            await Database.instance.set_autoproxy_preference(uid, guild, setting.id, expiration)
            await context.reply(f"Autoproxying as **{setting.name}** {postfix}.")


    @hook_command("who")
    async def _(context: Context):
        if not (ref := await context.message.get_reference()):
            await context.reply("Error: reply to a proxied message to use this command.")
            return

        lnk = await Database.instance.get_message_link(ref.id, ref.channel_id)
        if lnk:
            if proxy := await Database.instance.get_proxy(lnk.proxy_id):
                e = Embed(
                    "Proxied Message",
                    f"**Proxy**: {proxy.name}\n**Owner**: <@{lnk.platform_user}> (`{lnk.platform_user}`)\n**Message Link**: [link]({ref.mention})\n**Message**:\n{'\n'.join(('> ' + ln) for ln in ref.content.split('\n'))}"
                )
                dm = await context.author.get_dm()
                await dm.send("", [e])
                await context.message.delete()
                return

        await context.reply("Error: that message is not a proxied message!")


    @hook_command("delete")
    async def _(context: Context, bypass: bool):
        if not (ref := await context.message.get_reference()):
            await context.reply("Error: reply to a proxied message to use this command.")
            return

        lnk = await Database.instance.get_message_link(ref.id, ref.channel_id)
        if lnk:
            bypasses = bypass and (await context.channel.permissions_for(await context.get_member(context.author.id))).manage_messages

            if (proxy := await Database.instance.get_proxy(lnk.proxy_id)) and (bypasses or proxy.owner == await get_uid(context)):
                await Database.instance.delete_link_message(ref.id, ref.channel_id)
                await ref.delete()
                await context.message.delete()
                return

            await context.reply("Error: you do not own this proxy!")
            return

        await context.reply("Error: that message is not a proxied message!")

