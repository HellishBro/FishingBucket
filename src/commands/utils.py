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


def get_proxies_text(bunch: list[Proxy], user_preference: UserPreference, detailed = False, length_limit = 4096, display_group: bool = True) -> tuple[str, int]:
    def list_fields(prox: Proxy) -> str:
        lns = []
        if (user_preference.public_group or detailed) and display_group:
            lns.append(f"- Group: {prox.group.name if prox.group else '*N/A*'}")
        if user_preference.public_trigger or detailed:
            lns.append(f"- Triggers: {', '.join(f'`{trigger}`' for trigger in prox.triggers) if prox.triggers and any(bool(t) for t in prox.triggers) else '*N/A*'}")
        lns.append(f"- Avatar: [source]({prox.avatar_url})")
        if user_preference.public_forms or detailed:
            if prox.forms:
                lns.append(f"- Forms:")
                for fname, furl in prox.forms.items():
                    lns.append(f"    - {fname}: [avatar]({furl}){' (current)' if prox.current_form == fname else ''}")

        if user_preference.public_metadata or detailed:
            lns.append(f"- Messages Send: {prox.times_used}")
            lns.append(f"- Creation Date: {format_date(datetime.fromtimestamp(prox.creation_date))}")
        if user_preference.public_description or detailed:
            if prox.description:
                lns.append("- Description:")
                for ln in prox.description.split("\n"):
                    lns.append(f"> {ln}")
        return "\n".join(lns)

    lines = []
    chars = 0
    i = 0
    for i, proxy in enumerate(bunch):
        line = f"**{proxy.name}**{(' (aka **' + proxy.nickname + '**)') if proxy.nickname else ''} (`{proxy.id}`)\n{list_fields(proxy)}"
        if chars + len(line) > length_limit:
            if chars == 0:
                return line[:length_limit - 3] + "...", 1
            i -= 1
            break
        lines.append(line)
        chars += len(line) + 2

    return "\n\n".join(lines), i + 1


async def paged_proxy_list(context: Context, proxies: list[Proxy], title: str, page: int, detailed: bool, additional_embeds: list[Embed] = None):
    if not proxies:
        await context.reply("", [Embed(
            f"{title} (0 total)",
            f"It's as empty as a desert out here...\n\nTry running `{get_command_invocation('register')}` to get started!"
        )] + (additional_embeds or []))
        return

    preferences = await Database.instance.get_user_preferences(await get_uid(context))

    if not (preferences.public_list or detailed):
        await context.reply("", [Embed(
            f"{title} (? total)",
            f"This proxy list cannot be viewed."
        )] + (additional_embeds or []))
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
            pages.extend(get_smart_pages(group_proxies, lambda section: get_proxies_text(section, preferences, detailed, length_limit, False), page_fore + "\n\n"))

        group_proxies = [proxy for proxy in proxies if proxy.group is None]
    else:
        group_proxies = proxies

    pages.extend(get_smart_pages(group_proxies, lambda section: get_proxies_text(section, preferences, detailed, 4096, False)))

    await paged(
        context,
        f"{title} ({len(proxies)} total)",
        pages,
        page,
        additional_embeds
    )


async def paged(context: Context, title: str, pages: list[str], start_page: int, additional_embeds: list[Embed] = None):
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

        reply_ctx = await context.reply("", [embed] + (additional_embeds or []))
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
                await message.edit("", embeds=[await get_page(page)] + (additional_embeds or []))

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