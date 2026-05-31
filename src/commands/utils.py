from ..interaction import Interactions, Interaction
from ..service import Context, Embed, ReactionActionEvent


async def paged(context: Context, title: str, pages: list[str], start_page: int):
    LEFT, RIGHT = "⬅️", "➡️"

    author = context.author.id

    async def get_page(p: int) -> Embed | None:
        if not 0 <= p < len(pages):
            await context.reply(f"Page {p + 1} is out of range 1~{len(pages)}")
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
                    await message.remove_reaction(RIGHT, author)
                    if page == 0:
                        await message.add_reaction(LEFT)
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
