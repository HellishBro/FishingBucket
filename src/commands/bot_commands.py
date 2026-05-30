from datetime import datetime

from .generic import hook_command, get_commands
from ..backend.config import Config
from ..backend.data_reader import DataReader
from ..backend.template_utils import Template
from ..service import Platform, FluxerContext, DiscordContext, IntersectionContext


def setup():
    @hook_command("ping", Platform.Fluxer)
    async def _(context: FluxerContext):
        stime = datetime.fromisoformat(context.message.timestamp)
        m = await context.reply(f"Pong! Latency is calculating! :ping_pong:")
        etime = datetime.fromisoformat(m.timestamp)
        diff = etime - stime
        await m.edit(f"Pong! Latency is {int(diff.microseconds / 1000)} ms! :ping_pong:")

    @hook_command("ping", Platform.Discord)
    async def _(context: DiscordContext):
        stime = context.message.created_at
        m = await context.reply(f"Pong! Latency is calculating! :ping_pong:")
        etime = m.created_at
        diff = etime - stime
        await m.edit(content=f"Pong! Latency is {int(diff.microseconds / 1000)} ms! :ping_pong:")


    @hook_command("invite")
    async def _(context: IntersectionContext):
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
            context.Embed(
                "Invite Me!",
                description
            )
        ])


    @hook_command("help")
    async def _(context: IntersectionContext, topic: str | None):
        if topic is None:
            await context.reply("", [context.Embed(
                "Help",
                Template.from_string(DataReader.instance["help.md"]).compute({
                    "config": Config.instance
                }, "")
            )])

        commands = get_commands()
        if topic in commands:
            await context.reply("\n".join(commands[topic].get_example_invocation() for _ in range(10)))
