from datetime import datetime
from typing import Callable

from .generic import get_command_invocation
from .specific import get_uid
from ..backend.database import Database, UserPreference
from ..backend.models import Proxy
from ..backend.template_utils import Template, TextPart
from ..backend.utils import format_date
from ..interaction import Interactions, Interaction
from ..service import Context, Embed, ReactionActionEvent


def get_smart_pages[T](everything: list[T], function: Callable[[list[T]], tuple[str, int]], page_preface: str = "") -> list[str]:
    pages = []
    i = 0
    while i < len(everything):
        naive_section = everything[i: i + 5]
        res, succession = function(naive_section)
        if res:
            pages.append(page_preface + res)
        i += succession

    return pages


def get_proxies_text(bunch: list[Proxy], user_preference: UserPreference, detailed = False, length_limit = 4096) -> tuple[str, int]:
    def list_fields(proxy: Proxy) -> str:
        lines = []
        if (not user_preference.private_group or detailed) and len(bunch) == 1:
            lines.append(f"- Group: {proxy.group.name if proxy.group else '*N/A*'}")
        if not user_preference.private_trigger or detailed:
            lines.append(f"- Triggers: {', '.join(f'`{trigger}`' for trigger in proxy.triggers) if proxy.triggers and any(bool(t) for t in proxy.triggers) else '*N/A*'}")
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

    lines = []
    chars = 0
    i = 0
    for i, proxy in enumerate(bunch):
        line = f"**{proxy.name}**{(' (aka **' + proxy.nickname + '**)') if proxy.nickname else ''} (`{str(hex(proxy.id))[2:]}`)\n{list_fields(proxy)}"
        if chars + len(line) > length_limit:
            if chars == 0:
                return line[:length_limit - 3] + "...", 1
            i -= 1
            break
        lines.append(line)
        chars += len(line) + 2

    return "\n\n".join(lines), i + 1


async def paged_proxy_list(context: Context, proxies: list[Proxy], title: str, page: int, detailed: bool):
    if not proxies:
        await context.reply("", [Embed(
            f"{title} (0 total)",
            f"It's as empty as a desert out here...\n\nTry running `{get_command_invocation('register')}` to get started!"
        )])
        return

    preferences = await Database.instance.get_user_preferences(await get_uid(context))

    if not (preferences.public_list or detailed):
        await context.reply("", [Embed(
            f"{title} (? total)",
            f"This proxy list cannot be viewed."
        )])
        return

    pages = []
    if preferences.public_group or detailed:
        groups = set(proxy.group for proxy in proxies)
        if None in groups: groups.remove(None)
        groups = sorted(groups, key=lambda g: g.id)
        for group in groups:
            group_proxies = [proxy for proxy in proxies if proxy.group is group]

            page_fore = f"**Group**: {group.name}"

            if group.description:
                page_fore += "\n"
                for line in group.description.split("\n"):
                    page_fore += "\n> " + line

            length_limit = 4096 - len(page_fore)
            pages.extend(get_smart_pages(group_proxies, lambda section: get_proxies_text(section, preferences, detailed, length_limit), page_fore + "\n\n"))

        group_proxies = [proxy for proxy in proxies if proxy.group is None]
    else:
        group_proxies = proxies

    pages.extend(get_smart_pages(group_proxies, lambda section: get_proxies_text(section, preferences, detailed, 4096)))

    await paged(
        context,
        f"{title} ({len(proxies)} total)",
        pages,
        page
    )


async def paged(context: Context, title: str, pages: list[str], start_page: int):
    LEFT, RIGHT = "⬅️", "➡️"

    author = context.author.id

    async def get_page(p: int) -> Embed | None:
        if not 0 <= p < len(pages):
            await context.reply(f"Error: page {p + 1} is out of range 1~{len(pages)}")
            return None

        description = f"Page {p + 1} / {len(pages)}\n\n" + pages[p]
        return Embed(
            title,
            description
        )

    if embed := await get_page(start_page):
        page = start_page

        reply_ctx = await context.reply("", [embed])
        message = reply_ctx.message

        async def callback(event: ReactionActionEvent):
            nonlocal page

            if event.emoji in (LEFT, RIGHT):
                if event.emoji == LEFT:
                    await message.remove_reaction(LEFT, author)
                    if page == len(pages) - 1:
                        await message.add_reaction(RIGHT)
                    page -= 1
                else:
                    if page == 0:
                        await message.remove_reaction(RIGHT)
                        await message.add_reaction(LEFT)
                        await message.add_reaction(RIGHT)
                    else:
                        await message.remove_reaction(RIGHT, author)
                    page += 1
                page = max(min(page, len(pages) - 1), 0)
                await message.edit("", embeds=[await get_page(page)])

            if len(pages) != 1:
                if page == len(pages) - 1:
                    await message.remove_reaction(RIGHT)
                elif page == 0:
                    await message.remove_reaction(LEFT)

        Interactions.instance.add_interaction(
            reply_ctx,
            Interaction(author, callback, pop_after_use=False)
        )

        if len(pages) != 1:
            if page != 0:
                await message.add_reaction(LEFT)
            if page != len(pages) - 1:
                await message.add_reaction(RIGHT)


def example_trigger_text(trigger: Template) -> str:
    res = ""
    for part in trigger.parts:
        if isinstance(part, TextPart):
            res += part.content
        else:
            res += "hello"
    return res