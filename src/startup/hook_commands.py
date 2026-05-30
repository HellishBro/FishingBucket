from ..commands.generic import hook_command
from ..service import Context


def setup():
    @hook_command("help")
    async def help_command(context: Context, page_or_concept: int | str):
        await context.reply(f"You requested help for: {page_or_concept!r}")