from datetime import datetime

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
