import time
import fluxer
from fluxer.models import RawReactionActionEvent

from .utils import proxy_username, ensure_own_proxy, paged_group_list, ensure_own_group, paged_proxy_list, \
    valid_template
from .. import response
from ..backend.database import Database
from ..commands import register_command, register_group
from ..interaction import Interaction, remove_reaction, Interactions
from ..backend.models import optional_type, one_or_more, ProxyGroup, Proxy
from ..backend.utils import get_guild_id_from_channel


def setup(bot: fluxer.Bot):
    register_group("group", "Proxy Group Commands", "Commands related to creating and adjusting proxy groups.")

    @register_command([proxy_username, optional_type(str)], bot, "group register", """
    Creates a new proxy group.
    Groups help you organize different proxies that are related in some way.
    """, "group register <name> [description]",
                      ['group register "The Boys"', 'group register "The Girls" "Powerpuff Girls but grown up"',
                       'group register "The System"'], "group")
    async def group_register(message: fluxer.Message, name: str, description: str | None):
        description = description or ""
        g = await Database.instance.put_group(ProxyGroup(None, name, description, message.author.id, time.time(), "", None))
        await response.respond(message, "", [fluxer.Embed(
            "Group Registered!",
            f"The group **{name}** (`{str(hex(g.id))[2:]}`) has been registered{(' with the description:\n' + '\n'.join('> ' + l for l in description.split('\n'))) if description else '.'}"
        )])

    @register_command([optional_type(int)], bot, "group list", """
    Lists your proxy groups.
    This will only list the groups themselves, not the proxies in the groups.
    """, "group list [page]", ["group list", "group list 2"], "group")
    async def group_list(message: fluxer.Message, page: int | None):
        detailed = False
        if (await get_guild_id_from_channel(bot, message.channel_id)) is None:
            detailed = True

        await paged_group_list(message, await Database.instance.get_user_groups(message.author.id),
                               f"Proxy Groups of {message.author.display_name}", page, detailed)

    @register_command([str, optional_type(int)], bot, "group members", """
    Views all members that belonged to a group.
    """, "group members <group> [page]", ["group members 2d7", "group members 2d7 5"], "group")
    async def group_members(message: fluxer.Message, group_id: str, page: int | None):
        if not (group := await ensure_own_group(message, group_id)): return
        proxies = await Database.instance.get_user_proxies(message.author.id)
        filtered = [proxy for proxy in proxies if proxy.group and proxy.group.id == group.id]
        detailed = False
        if (await get_guild_id_from_channel(bot, message.channel_id)) is None:
            detailed = True

        await paged_proxy_list(message, filtered, f"Proxies of {message.author.display_name} in {group.name}", page, detailed)


    @register_command([str, one_or_more(str)], bot, "group add", """
    Adds proxies to a proxy group.
    Each proxy can only belong in one proxy group. To remove a proxy from its group, use `group ungroup`.
    """, 'group add <group> <proxy(s)>', ["group add 2d7 69ed73"], "group")
    async def group_add(message: fluxer.Message, group_id: str, proxy_ids: list[str]):
        if not (group := await ensure_own_group(message, group_id)): return
        proxies = []
        for proxy in proxy_ids:
            if p := await ensure_own_proxy(message, proxy):
                proxies.append(p)
            else:
                return
        for proxy in proxies:
            await Database.instance.update_group(proxy.id, group.id)
        ies = "y" if len(proxies) == 1 else "ies"
        s = "" if len(proxies) == 1 else "s"
        are = "is" if len(proxies) == 1 else "are"
        await response.respond(message, "", [fluxer.Embed(
            f"Prox{ies} Updated!",
            f"The group{s} for {len(proxies)} prox{ies} has been updated to **{group.name}**! The affected prox{ies} {are} {', '.join('*' + p.name + '*' for p in proxies)}"
        )])

    @register_command([str, one_or_more(str)], bot, "group add group", """
    Adds groups to a proxy group.
    This enables nested groups. To remove a group from its group, use `group ungroup group`.
    """, 'group add group <group> <group(s)>', ["group add 2d7 2d8 2d9"], "group")
    async def group_add_group(message: fluxer.Message, group_id: str, group_ids: list[str]):
        if not (group := await ensure_own_group(message, group_id)): return
        groups = []
        for g in group_ids:
            if p := await ensure_own_group(message, g):
                groups.append(p)
            else:
                return
        for g in groups:
            await Database.instance.update_group_parent(g.id, group.id)
        s = "" if len(groups) == 1 else "s"
        are = "is" if len(groups) == 1 else "are"
        await response.respond(message, "", [fluxer.Embed(
            f"Group{s} Updated!",
            f"The group{s} for {len(groups)} group{s} has been updated to **{group.name}**! The affected group{s} {are} {', '.join('*' + g.name + '*' for g in groups)}"
        )])

    @register_command([one_or_more(str)], bot, "group ungroup", """
    Ungroups proxies from their proxy groups.
    This will make the proxies listed uncategorized.
    """, "group ungroup <proxy(s)>", ["group ungroup 69ed73"], "group")
    async def group_ungroup(message: fluxer.Message, proxy_ids: list[str]):
        proxies = []
        for proxy in proxy_ids:
            if p := await ensure_own_proxy(message, proxy):
                proxies.append(p)
            else:
                return
        for proxy in proxies:
            await Database.instance.update_group(proxy.id, None)

        ies = "y" if len(proxies) == 1 else "ies"
        s = "" if len(proxies) == 1 else "s"
        are = "is" if len(proxies) == 1 else "are"
        await response.respond(message, "", [fluxer.Embed(
            f"Prox{ies} Updated!",
            f"The group{s} {are} ungrouped for {len(proxies)} prox{ies}! The affected prox{ies} {are} {', '.join('*' + p.name + '*' for p in proxies)}"
        )])

    @register_command([one_or_more(str)], bot, "group ungroup group", """
    Ungroups groups from their groups.
    """, "group ungroup group <group(s)>", ["group ungroup 2d8 2d9"], "group")
    async def group_ungroup(message: fluxer.Message, group_ids: list[str]):
        groups = []
        for g in group_ids:
            if p := await ensure_own_group(message, g):
                groups.append(p)
            else:
                return
        for g in groups:
            await Database.instance.update_group_parent(g.id, None)

        s = "" if len(groups) == 1 else "s"
        are = "is" if len(groups) == 1 else "are"
        await response.respond(message, "", [fluxer.Embed(
            f"Group{s} Updated!",
            f"The group{s} {are} ungrouped for {len(groups)} group{s}! The affected group{s} {are} {', '.join('*' + g.name + '*' for g in groups)}"
        )])

    @register_command([str], bot, "group remove", """
    Removes a proxy group that you own.
    All proxies within the group will be automatically ungrouped.
    """, "group remove <group>", ["group remove 2d7"], "group")
    async def proxy_remove(message: fluxer.Message, id_: str):
        group = await ensure_own_group(message, id_)
        if not group: return

        m = await response.respond(message,
                                   f"> [!WARNING]\n> Are you sure you want to remove group **{group.name}**? React to the :white_check_mark: to confirm. This message will expire in 30 seconds.")
        await m.add_reaction("✅")
        msg_id = int(m.id)

        async def cb(event: RawReactionActionEvent):
            if event.emoji.name == "✅":
                await Database.instance.delete_group(group.id)
                await response.respond(message, f"Successfully removed group **{group.name}**!")

        Interactions.instance.add_interaction(msg_id, Interaction(message.author.id, cb, 30))

        if await Interactions.instance.wait_claim_after(30, msg_id, message.author.id):
            await m.edit("Group remove confirmation expired!")
            await remove_reaction(m, "✅")

    @register_command([str, proxy_username], bot, "group name", """
    Updates a proxy group's name.
    """, "group name <group> <new name>", ['group name 2d7 "The Radicals"'], "group")
    async def group_name(message: fluxer.Message, id_: str, new_name: str):
        group = await ensure_own_group(message, id_)
        if not group: return

        old_name = group.name
        await Database.instance.update_group_name(group.id, new_name)
        embed = fluxer.Embed(
            "Group Updated!",
            f"The name for the previous *{old_name}* has been changed to **{new_name}**!"
        )
        await response.respond(message, "", [embed])

    @register_command([str, optional_type(proxy_username)], bot, "group tag", """
    Updates a proxy group's tag.
    A tag appears in the proxy name of that group. A proxy tag must contain the literal `{}` as the placeholder for the proxy's name, similar to proxy triggers.
    If not provided, the proxy tag will be cleared.
    """, "group tag <group> [proxy tag]", ['group tag 2d7 "{} | TR"'], "group")
    async def group_tag(message: fluxer.Message, id_: str, new_tag: str):
        group = await ensure_own_group(message, id_)
        if not group: return

        if not await valid_template(message, "Tag", new_tag): return

        await Database.instance.update_group_tag(group.id, new_tag)
        example_proxy = Proxy(None, "Example Proxy", "This is an example proxy", Proxy.random_avatar(), ["{}"], 0, 0, 0, group, None)
        embed = fluxer.Embed(
            "Group Updated!",
            f"The tag for *{group.name}* has been changed! Proxies sent using this group will have their name be displayed as **{example_proxy.effective_name}**"
            if new_tag else f"The tag for *{group.name}* has been cleared!"
        )
        await response.respond(message, "", [embed])

    @register_command([str, str], bot, "group description", """
    Updates a proxy group's description.
    """, "group description <group> <new description>",
                      ['group description 2d7 Seven days ago, on a faithful day...'], "group")
    async def group_name(message: fluxer.Message, id_: str, new_description: str):
        group = await ensure_own_group(message, id_)
        if not group: return

        await Database.instance.update_group_description(group.id, new_description)
        embed = fluxer.Embed(
            "Group Updated!",
            f"The previous description for **{group.name}** has been changed! New description:\n" + "\n".join(
                "> " + line for line in new_description.split("\n"))
        )
        await response.respond(message, "", [embed])