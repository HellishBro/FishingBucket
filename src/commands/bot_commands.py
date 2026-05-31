from .generic import hook_command, get_commands, get_command_groups, strategize
from .utils import paged
from ..backend.config import Config
from ..backend.data_reader import DataReader
from ..backend.template_utils import Template
from ..service import Platform, Context, Embed


def setup():
    @hook_command("ping")
    async def _(context: Context):
        stime = context.message.timestamp
        m = await context.reply(f"Pong! Latency is calculating! :ping_pong:")
        etime = m.message.timestamp
        diff = etime - stime
        await m.message.edit(f"Pong! Latency is {int(diff.microseconds / 1000)} ms! :ping_pong:")


    @hook_command("invite")
    async def _(context: Context):
        def get_invites(plat: Platform) -> tuple[str, str]:
            return (
                Config.instance.bot_invite if plat == Platform.Fluxer else Config.instance.discord.bot_invite,
                Config.instance.server_invite if plat == Platform.Fluxer else Config.instance.discord.server_invite
            )

        bot_invite, server_invite = get_invites(context.platform)
        description = f"Use [this link]({bot_invite}) to invite me to your community!\nSupport community invite: {server_invite}."

        if len(Platform) > 1:
            description += "\n\n"
            parts = []
            for platform in Platform:
                if platform != context.platform:
                    b, s = get_invites(platform)
                    parts.append(f"Come join us on {platform.name}! [Invite bot]({b}) and [join community]({s})!")
            description += "\n".join(parts)

        await context.reply("", embeds=[
            Embed(
                "Invite Me!",
                description
            )
        ])


    @hook_command("help")
    async def _(context: Context, topic: str | None):
        if topic is None:
            pages = [
                Template.from_string(DataReader.instance["help.md"]).compute({
                    "config": Config.instance
                }, "")
            ]
            for group_id, group in get_command_groups().items():
                page = f"**{group.brief}** (`{group.canonical_name}`): {group.description}\n"
                for cmd_id in group.commands:
                    cmd = get_commands()[cmd_id]
                    page += f"\n- `{Config.instance.prefixes[0]}{cmd.get_usage(strategize)}` - {cmd.brief}"
                pages.append(page)

            await paged(
                context,
                "Help",
                pages,
                0
            )
            return

        commands = get_commands()
        if topic in commands:
            await context.reply("\n".join(commands[topic].get_example_invocation() for _ in range(10)))
