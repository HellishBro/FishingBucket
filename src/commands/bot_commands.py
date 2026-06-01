from datetime import datetime
from typing import Any

from .generic import hook_command, get_commands, get_command_groups, strategize, Command, CommandGroup, \
    get_session_command_usages, get_command_invocation
from .utils import paged
from ..backend.cache import CacheStatus
from ..backend.config import Config
from ..backend.data_reader import DataReader
from ..backend.database import Database
from ..backend.template_utils import Template
from ..service import Platform, Context, Embed


def setup():
    start_time = datetime.now()

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
        def get_description(thing: Command | CommandGroup) -> str:
            desc = thing.description.strip()
            result = []
            for line in desc.split("\n"):
                result.append(line.strip())
            return "\n".join(result)

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
                    page += f"\n- `{get_command_invocation(cmd_id)}` - {cmd.brief}"
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
            command = commands[topic]
            description = f"**Usage**: `{Config.instance.prefixes[0]}{command.get_usage(strategize)}`\n\n{get_description(command)}\n\n**Examples**:"
            examples = []
            for _ in range(10):
                example = command.get_example_invocation()
                if example not in examples:
                    examples.append(example)

                if len(examples) == 3:
                    break

            for example in sorted(examples, key=len):
                description += f"\n- `{Config.instance.prefixes[0]}{example}`"

            await context.reply("", [Embed(f"Help: {Config.instance.prefixes[0]}{topic}", description)])
            return

        groups = get_command_groups()
        if topic in groups:
            group = groups[topic]
            description = f"**{group.brief}** (`{group.canonical_name}`): {group.description}\n"
            for cmd_id in group.commands:
                cmd = get_commands()[cmd_id]
                description += f"\n- `{Config.instance.prefixes[0]}{cmd.get_usage(strategize)}` - {cmd.brief}"

            await context.reply("", [Embed(f"Help: {group.brief}", description)])
            return


    @hook_command("stats")
    async def _(context: Context, stat: str | None):
        cache_efficiency_denominator = CacheStatus.instance.hits + CacheStatus.instance.misses
        all_stats: dict[str, Any] = await Database.instance.get_global_stats()
        all_stats.update({
            "uptime": datetime.now() - start_time,
            "guilds": len(context.bot.guilds),
            "cache_efficiency": (CacheStatus.instance.hits / cache_efficiency_denominator) if cache_efficiency_denominator != 0 else 1,
            "invocations": get_session_command_usages(),
            "commands": len(get_commands())
        })
        all_stats["uptime"] = datetime.now() - start_time
        mapping = {
            "guilds": ("Total community count", lambda n: int(n)),
            "uptime": ("Uptime", lambda td: td),
            "commands": ("Total commands", lambda n: int(n)),
            "proxy_uses": ("Total proxy uses", lambda n: int(n)),
            "total_proxies": ("Total registered proxies", lambda n: int(n)),
            "cache_efficiency": ("Cache efficiency", lambda n: f"{n * 100:.2f}%"),
            "invocations": ("Session command invocations", lambda n: int(n)),
            "version": ("Database version", lambda n: int(n))
        }
        if stat:
            if stat in all_stats:
                m = mapping.get(stat, (stat, lambda n: str(n)))
                await context.reply("", embeds=[Embed(
                    f"{Config.instance.name} Statistics",
                    f"**{m[0]}** (`{stat}`): {m[1](all_stats[stat])}"
                )])
            else:
                await context.reply(f"Error! `{stat}` is not recognized as a tracked statistic!")
        else:
            await context.reply("", embeds=[Embed(
                f"{Config.instance.name} Statistics",
                "\n".join(f"**{(m := mapping.get(stat, (stat, lambda n: str(n))))[0]}** (`{stat}`): {m[1](all_stats[stat])}" for stat in all_stats)
            )])