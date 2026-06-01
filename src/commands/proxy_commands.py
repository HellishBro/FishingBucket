from datetime import datetime

from textdistance import damerau_levenshtein as edit_distance

from .generic import hook_command
from .specific import get_uid
from .utils import example_trigger_text, paged_proxy_list
from ..backend.database import Database
from ..backend.models import Proxy
from ..backend.template_utils import Template
from ..backend.utils import normalize_emojis
from ..service import Context, Embed


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
