import math
from datetime import datetime
import fluxer
from fluxer.models import RawReactionActionEvent
from textdistance import damerau_levenshtein

from ..interaction import Interaction, Interactions, remove_reaction
from .. import response
from ..backend.database import Database, UserPreference
from ..backend.models import Proxy, ProxyGroup, string_with_length
from ..backend.template_utils import Template, TextPart, ExprPart
from ..backend.utils import format_date, get_member, compute_permissions, normalize_emojis

bot: fluxer.Bot = None
proxy_username = string_with_length(50)
def set_consts(bot_: fluxer.Bot):
    global bot
    bot = bot_


async def paged(initiator: fluxer.Message, title: str, pages: list[str], page: int | None):
    page = page or 1
    author = initiator.author.id

    async def get_page(p: int) -> fluxer.Embed | None:
        if not 0 <= p < len(pages):
            await initiator.reply(
                f"Page {p + 1} is out of bounds! There is a maximum of {len(pages)} page{'s' if len(pages) != 1 else ''}."
            )
            return None

        description = f"Page {p + 1} / {len(pages)}\n\n" + pages[p]
        return fluxer.Embed(
            title,
            description
        )

    actual_page = page - 1
    had_left = False

    async def cb(event: RawReactionActionEvent):
        nonlocal actual_page, had_left
        if event.emoji.name in ("⬅️", "➡️"):
            if event.emoji.name == "⬅️":
                await remove_reaction(m, "⬅️", event.user_id)
                actual_page -= 1
            else:
                await remove_reaction(m, "➡️", event.user_id)
                actual_page += 1
            actual_page = max(min(actual_page, len(pages) - 1), 0)
            await m.edit("", embeds=[(await get_page(actual_page)).to_dict()])
            if 0 <= actual_page < len(pages):
                if 0 < actual_page:
                    if actual_page < len(pages) and not had_left:
                        await remove_reaction(m, "➡️")
                    await m.add_reaction("⬅️")
                    had_left = True
                    if actual_page < len(pages) and not had_left:
                        await m.add_reaction("➡️")
                else:
                    await remove_reaction(m, "⬅️")
                    had_left = False
                if actual_page + 1 < len(pages):
                    await m.add_reaction("➡️")
                else:
                    await remove_reaction(m, "➡️")

    if embed := await get_page(actual_page):
        m = await response.respond(initiator, "", [embed])

        if 0 <= actual_page < len(pages):
            Interactions.instance.add_interaction(m.id, Interaction(author, cb))

            if 0 < actual_page:
                await m.add_reaction("⬅️")
                had_left = True
            if actual_page + 1 < len(pages):
                await m.add_reaction("➡️")


def get_proxies_text(bunch: list[Proxy], user_preference: UserPreference, detailed = False):
    def list_fields(proxy: Proxy) -> str:
        lines = []
        if (not user_preference.private_group or detailed) and len(bunch) == 1:
            lines.append(f"- Group: {proxy.group.name if proxy.group else '*N/A*'}")
        if not user_preference.private_trigger or detailed:
            lines.append(f"- Triggers: {', '.join(f'`{trigger}`' for trigger in proxy.triggers) if proxy.triggers else '*N/A*'}")
        lines.append(f"- Avatar: [source]({proxy.avatar_url})")
        if not user_preference.private_forms or detailed:
            if proxy.forms:
                lines.append(f"- Forms:")
                for fname, furl in proxy.forms.items():
                    lines.append(f"    - {fname}: [avatar]({furl}){' (current)' if proxy.current_form == fname else ''}")

        if not user_preference.private_metadata or detailed:
            lines.append(f"- Messages Send: {proxy.times_used}")
            lines.append(f"- Creation Date: {format_date(datetime.fromtimestamp(proxy.creation_date))}")
        if not user_preference.private_description or detailed:
            if proxy.description:
                lines.append("- Description:")
                for line in proxy.description.split("\n"):
                    lines.append(f"> {line}")
        return "\n".join(lines)

    return "\n\n".join(
        f"**{proxy.name}**{(' (aka **' + proxy.nickname + '**)') if proxy.nickname else ''} (`{str(hex(proxy.id))[2:]}`)\n{list_fields(proxy)}"
        for proxy in bunch
    )

async def paged_proxy_list(message: fluxer.Message, proxies: list[Proxy], title: str, page: int | None, detailed = False):
    if len(proxies):
        preferences = await Database.instance.get_user_preferences(message.author.id)
        pages = []
        show_groups = not preferences.private_group or detailed
        if show_groups:
            groups = set(proxy.group for proxy in proxies)
            if None in groups: groups.remove(None)
            groups = sorted(groups, key=lambda g: g.id)
            for group in groups:
                description = ("\n" + "\n".join("> " + line for line in group.description.split("\n"))) if group.description else ""
                group_proxies = [proxy for proxy in proxies if proxy.group == group]
                group_pages = [
                    ((f"**Group**: {group.name}" + description + "\n\n") if show_groups else "") + get_proxies_text(group_proxies[p * 5 : p * 5 + 5], preferences, detailed)
                    for p in range(math.ceil(len(group_proxies) / 5))
                ]
                pages.extend(group_pages)

            group_proxies = [proxy for proxy in proxies if proxy.group is None]
        else:
            group_proxies = proxies
        pages.extend([
            get_proxies_text(group_proxies[p * 5 : p * 5 + 5], preferences)
            for p in range(math.ceil(len(group_proxies) / 5))
        ])
        await paged(message, f"{title} ({len(proxies)} total)", pages, page)
    else:
        await message.reply("", embeds=[fluxer.Embed(
            f"{title} (0 total)",
            f"It's as empty as a desert out here...\n\nTry running `{bot.command_prefix}register` to get started!"
        ).to_dict()])


async def get_group_text(bunch: list[ProxyGroup], user_preference: UserPreference, detailed = False):
    def list_fields(group: ProxyGroup) -> str:
        lines = []
        if group.tag:
            lines.append(f"- Tag: `{group.tag}`")
        if not user_preference.private_metadata or detailed:
            lines.append(f"- Creation Date: {format_date(datetime.fromtimestamp(group.creation_date))}")
        if not user_preference.private_description or detailed:
            if group.description:
                lines.append("- Description:")
                for line in group.description.split("\n"):
                    lines.append(f"> {line}")
        if not user_preference.private_group or detailed:
            if group.parent:
                lines.append(f"- Parent Group: {group.parent.name} (`{str(hex(group.parent.id))[2:]}`)")
        return "\n".join(lines)

    group_members = {}
    for group in bunch:
        group_members[group.id] = await Database.instance.get_group_member_count(group.id)

    return "\n\n".join(
        f"**{group.name}** (`{str(hex(group.id))[2:]}`): {group_members[group.id]} proxies\n{list_fields(group)}"
        for group in bunch
    )

async def paged_group_list(message: fluxer.Message, groups: list[ProxyGroup], title: str, page: int | None, detailed = False):
    if len(groups):
        preferences = await Database.instance.get_user_preferences(message.author.id)
        pages = [
            await get_group_text(groups[g * 10: g * 10 + 10], preferences, detailed)
            for g in range(math.ceil(len(groups) / 10))
        ]
        await paged(message, f"{title} ({len(groups)} total)", pages, page)
    else:
        await message.reply("", embeds=[fluxer.Embed(
            f"{title} (0 total)",
            f"It's as empty as a desert out here...\n\nTry running `{bot.command_prefix}group register` to get started!"
        ).to_dict()])


async def require_reply(message: fluxer.Message) -> fluxer.Message | None:
    if not message.referenced_message:
        m = await response.respond(message, "Reply to a message to use this command! This message will expire in 15 seconds.")
        if await Interactions.instance.wait_claim_after(15, m.id, m.author.id):
            await response.delete_message(m)
            await message.delete()
        return None
    return message.referenced_message


async def require_permission(message: fluxer.Message, permission: int, name: str) -> bool:
    member = await get_member(message.guild_id, bot, message.author.id)
    perms = await compute_permissions(member, bot, message.channel)
    if perms & permission == permission:
        return True
    await response.respond(message, f"Error! You do not have the **{name}** permission!")
    return False

async def ensure_own_proxy(message: fluxer.Message, id_: str | int) -> Proxy | None:
    err = f"`{id_}` is not a valid proxy ID nor is it close to the name of a proxy that you own! Proxy IDs are hexadecimal numbers, usually written to the right of their names in the output of various commands."
    find_name = False
    proxy = None

    try:
        if isinstance(id_, str):
            proxy_id = int(id_, 16)
            if proxy_id > 2147483647:
                find_name = True
            else:
                proxy = await Database.instance.get_proxy(proxy_id)
        else:
            proxy = await Database.instance.get_proxy(id_)
    except ValueError:
        find_name = True

    if find_name:
        id_ = normalize_emojis(id_)
        valid_proxies = await Database.instance.get_user_proxies(message.author.id)
        distances = [min(damerau_levenshtein(id_.lower(), valid_proxy.name.lower()), damerau_levenshtein(id_.lower(), (valid_proxy.nickname or valid_proxy.name).lower())) for valid_proxy in valid_proxies]
        minimum = min(distances) if distances else 999
        if minimum > 5:
            await response.respond(message, err)
            return None
        idx = distances.index(minimum)
        proxy = valid_proxies[idx]

    if not proxy:
        await response.respond(message, "This proxy does not exist!")
        return None
    if proxy.owner != await Database.instance.get_user_id(message.author.id):
        await response.respond(message, "You do not own this proxy!")
        return None
    return proxy

async def ensure_own_group(message: fluxer.Message, id_: str | int) -> ProxyGroup | None:
    err = f"`{id_}` is not a valid group ID nor is it close to the name of a group that you own! Group IDs are hexadecimal numbers, usually written to the right of their names in the output of various commands."
    find_name = False
    group = None

    try:
        if isinstance(id_, str):
            group_id = int(id_, 16)
            if group_id > 2147483647:
                find_name = True
            else:
                group = await Database.instance.get_group(group_id)
        else:
            group = await Database.instance.get_group(id_)
    except ValueError:
        find_name = True

    if find_name:
        id_ = normalize_emojis(id_)
        valid_groups = await Database.instance.get_user_groups(message.author.id)
        distances = [damerau_levenshtein(id_.lower(), valid_group.name.lower()) for valid_group in valid_groups]
        minimum = min(distances) if distances else 999
        if minimum > 5:
            await response.respond(message, err)
            return None
        idx = distances.index(minimum)
        group = valid_groups[idx]

    if not group:
        await response.respond(message, "This group does not exist!")
        return None
    if group.owner != await Database.instance.get_user_id(message.author.id):
        await response.respond(message, "You do not own this group!")
        return None
    return group

async def valid_template(message: fluxer.Message, this: str, trigger: str, top_level_variables: list[str]) -> bool:
    try:
        template = Template.from_string(trigger)
        if template.errors:
            await response.respond(message, f"Warning: template reading encountered errors while parsing:\n{'\n'.join(('- ' + err) for err in template.errors)}")

        if template.get_expr_count() == 0:
            await response.respond(message, "Error! `" + this + "` must contain the literal `{}` or have an expression slot!")
            return False

        for part in template.parts:
            if isinstance(part, ExprPart):
                if part.content:
                    for top_level_variable in top_level_variables:
                        if top_level_variable in part.content:
                            return True
                    if len(top_level_variables) == 1:
                        await response.respond(message, f"Error! `{this}` must contain the top level variable `{top_level_variables}`, or leave empty.")
                    else:
                        await response.respond(message, f"Error! `{this}` must contain at least one of the top level variables: `{'`, `'.join(top_level_variables)}`, or leave empty.")
                    return False
    except TypeError as e:
        await response.respond(message, f"Error! {e}")
        return False
    return True

def example_trigger_text(trigger: str) -> str:
    template = Template.from_string(trigger)
    res = ""
    for part in template.parts:
        if isinstance(part, TextPart):
            res += part.content
        else:
            res += "hello"
    return res
