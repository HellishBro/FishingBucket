import time
from typing import Tuple, Literal

from .generic import hook_command
from .specific import get_uid
from .utils import paged_proxy_group_list, get_groups_text, paged_proxy_list
from ..backend.database import Database
from ..backend.models import ProxyGroup, Proxy
from ..backend.template_utils import Template
from ..backend.utils import normalize_emojis
from ..interaction import Interactions, Interaction
from ..service import Context, Embed, ReactionActionEvent


def setup():
    @hook_command("group register")
    async def _(context: Context, name: str, description: str):
        g = await Database.instance.put_group(
            ProxyGroup(
                None,
                name,
                description,
                await get_uid(context, True),
                time.time(),
                "",
                None
            )
        )
        embed = Embed(
            "Group Registered!",
            f"The group **{name}** (`{g.id}`) has been registered{(' with the description:\n' + '\n'.join('> ' + l for l in description.split('\n'))) if description else '.'}"
        )
        await context.reply("", [embed])


    @hook_command("group list")
    async def _(context: Context, page: int, detailed: bool):
        uid = await get_uid(context)

        await paged_proxy_group_list(
            context,
            await Database.instance.get_user_groups(uid),
            f"Proxy Groups of {context.author.display_name}",
            page,
            context.channel.dm or detailed
        )


    @hook_command("group info")
    async def _(context: Context, group: ProxyGroup, detailed: bool):
        embed = Embed(
            f"{group.name}",
            get_groups_text([group], await Database.instance.get_user_preferences(await get_uid(context)), context.channel.dm or detailed)[0]
        )
        await context.reply("", [embed])


    @hook_command("group members")
    async def _(context: Context, group: ProxyGroup, page: int, detailed: bool):
        uid = await get_uid(context)
        proxies = await Database.instance.get_user_proxies(uid)
        filtered = [proxy for proxy in proxies if proxy.group and proxy.group.id == group.id]

        await paged_proxy_list(
            context,
            filtered,
            f"Proxies of {context.author.display_name} in **{group.name}**",
            page,
            context.channel.dm or detailed
        )


    @hook_command("group name")
    async def _(context: Context, group: ProxyGroup, name: str):
        old_name = group.name
        await Database.instance.update_group_name(group.id, normalize_emojis(name))
        embed = Embed(
            "Group Updated!",
            f"The name for the previous *{old_name}* has been changed to **{name}**!"
        )
        await context.reply("", [embed])


    @hook_command("group tag")
    async def _(context: Context, group: ProxyGroup, tag: Template | None):
        t = normalize_emojis(tag.string)
        await Database.instance.update_group_tag(group.id, t)
        group.tag = t
        example_proxy = Proxy(None, "Example Proxy", "This is an example proxy", Proxy.random_avatar(), ["{}"], 0, 0, 0, group, None, {}, None)
        embed = Embed(
            "Group Updated!",
            f"The tag for *{group.name}* has been changed! Proxies sent using this group will have their name be displayed as **{example_proxy.effective_name}**"
            if tag else f"The tag for *{group.name}* has been cleared!"
        )
        await context.reply("", [embed])


    @hook_command("group description")
    async def _(context: Context, group: ProxyGroup, description: str):
        await Database.instance.update_group_description(group.id, description)
        embed = Embed(
            "Group Updated!",
            f"The previous description for **{group.name}** has been changed! New description:\n" + "\n".join(
                "> " + line for line in description.split("\n"))
        )
        await context.reply("", [embed])


    @hook_command("group add")
    async def _(context: Context, to: ProxyGroup, items: Tuple[Literal["proxies"], list[Proxy]] | Tuple[Literal["groups"], list[ProxyGroup]]):
        item_type, items_list = items
        if item_type == "proxies":
            for proxy in items_list:
                await Database.instance.update_group(proxy.id, to.id)
        elif item_type == "groups":
            for group in items_list:
                if await Database.instance.will_groups_cycle(group.id, to.id):
                    await context.reply(f"Error: could not group **{group.name}** to **{to.name}** as doing so will create a cyclic loop.")
                    return

            for group in items_list:
                await Database.instance.update_group_parent(group.id, to.id)

        await context.reply("", [Embed(
            "Added to Group!",
            f"Added **{'**, **'.join(item.name for item in items_list)}** to the group **{to.name}**."
        )])


    @hook_command("group remove")
    async def _(context: Context, from_: ProxyGroup, items: Tuple[Literal["proxies"], list[Proxy]] | Tuple[Literal["groups"], list[ProxyGroup]]):
        item_type, items_list = items
        if item_type == "proxies":
            for proxy in items_list:
                await Database.instance.update_group(proxy.id, None)
        elif item_type == "groups":
            for group in items_list:
                await Database.instance.update_group_parent(group.id, None)

        await context.reply("", [Embed(
            "Removed from Group!",
            f"Removed **{'**, **'.join(item.name for item in items_list)}** from the group **{from_.name}**."
        )])


    @hook_command("group delete")
    async def _(context: Context, group: ProxyGroup):
        m = await context.reply(f"> [!WARNING]\n> Are you sure you want to remove group **{group.name}**? React to the :white_check_mark: to confirm. This message will expire in 30 seconds.")
        await m.message.add_reaction("✅")

        async def cb(event: ReactionActionEvent) -> bool:
            if event.emoji == "✅":
                await Database.instance.delete_group(group.id)
                await m.reply(f"Successfully removed group **{group.name}**!")
                return True
            return False

        Interactions.instance.add_interaction(m, Interaction(context.author.id, cb))

        if await Interactions.instance.wait_claim_after(30, m.id, m.platform):
            await m.message.edit("Group delete confirmation expired.")
            await m.message.remove_reaction("✅")
