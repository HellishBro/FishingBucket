from ..service import Context, Embed


async def paged(context: Context, title: str, pages: list[str], start_page: int):
    author = context.author.id

    async def get_page(p: int):
        if not 0 <= p < len(pages):
            await context.reply(f"Page {p + 1} is out of range 1~{len(pages)}")
            return None

        description = f"Page {p + 1} / {len(pages)}\n\n" + pages[p]
        return Embed(
            title,
            description
        )
