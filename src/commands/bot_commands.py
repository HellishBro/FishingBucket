from datetime import datetime
from typing import Any

import fluxer

from .. import response, commands
from ..backend.data_reader import DataReader
from ..backend.database import Database
from ..backend.config import Config
from ..backend.cache import CacheStatus
from ..backend.template_utils import Template
from ..commands import register_command, register_group, command_groups
from .utils import paged
from ..backend.models import optional_type, alternative
from ..backend.utils import compute_permissions, get_member

start_time = datetime.now()

def setup(bot: fluxer.Bot):
    register_group("bot", "Bot Commands", "Commands related to the bot itself.")

    @register_command([optional_type(alternative(int, str))], bot, "help", """
    Provides information about this bot or about a command.
    Optional argument `command`. If provided, it will show the command description, usage, as well as examples.
    If instead, a `page` is provided, it will show that page of the help menu.
    """, "help [command OR page]", ["help", "help help", "help register", "help 2"], "bot", ["", "h", "?"])
    async def help_(message: fluxer.Message, command_or_page: str | int | None):
        if isinstance(command_or_page, str):
            command = command_or_page
            for group in command_groups.values():
                if any(com[0] == command for com in group.commands):
                    if (command, None) in group.commands:
                        cmd = group.commands[command, None]
                    else:
                        cmd = group.commands[command, False]
                    description = f"**Usage**: {bot.command_prefix}{cmd.usage}\n\n{cmd.description}\n\n**Examples**:\n"
                    description += "\n".join("- `" + bot.command_prefix + example + "`" for example in cmd.examples)
                    await response.respond(message, "", [fluxer.Embed(f"Help: {cmd.name}", description)])
                    return

            await response.respond(message, f"`{bot.command_prefix}{command}` is not recognized as a valid command! Use `{bot.command_prefix}help` to view all commands!")
        else:
            pages = [
                Template.from_string(DataReader.instance["help.md"]).compute({
                    "bot": bot,
                    "config": Config.instance
                }, "")
            ]
            for group in command_groups.values():
                page = f"**{group.name}**: {group.description}"
                for i, c in enumerate(group.commands.values()):
                    if c.editing != True: # c.editing may be None
                        page += f"\n- `{bot.command_prefix}{c.usage}` - {c.description.split('\n')[0]}"
                pages.append(page)

            await paged(message, f"Help: {Config.instance.name}", pages, command_or_page)


    @register_command([], bot, "ping", "Gets the bot's latency.", "ping", ["ping"], "bot", [], False)
    async def ping(message: fluxer.Message):
        stime = datetime.fromisoformat(message.timestamp)
        m = await response.respond(message, "Pong! Latency is calculating! :ping_pong:")
        end_time = datetime.fromisoformat(m.timestamp)
        diff = end_time - stime
        await m.edit(f"Pong! Latency is {int(diff.microseconds / 1000)}ms! :ping_pong:")

    @register_command([], bot, "ping", "Gets the bot's latency.", "ping", ["ping"], "bot", [], True)
    async def ping(message: fluxer.Message):
        stime = datetime.fromisoformat(message.timestamp)
        m = await response.respond(message, "Pong! Latency is calculating! :ping_pong:\nNote: The latency when editing messages is different from sending messages!")
        end_time = datetime.fromisoformat(m.timestamp)
        diff = end_time - stime
        await m.edit(f"Pong! Latency is {int(diff.microseconds / 1000)}ms! :ping_pong:\nNote: The latency when editing messages is different from sending messages!")


    @register_command([], bot, "invite", "Invite me to your community!", "invite", ["invite"], "bot")
    async def invite(message: fluxer.Message):
        await message.reply("", embeds=[fluxer.Embed(
            "Invite Me!",
            f"Use [this link]({Config.instance.bot_invite}) to invite me to your community!\nSupport community invite: [{Config.instance.server_invite}]({Config.instance.server_invite})."
        ).to_dict()])


    @register_command([optional_type(fluxer.Channel)], bot, "permissions", """
    Checks the bot's permissions.
    The permissions are required for this bot to function properly. If some permissions are missing, then that functionality will not work as expected.
    """, "permissions [channel]", ["permissions", "permissions #general"], "bot", ["perms"])
    async def permissions(message: fluxer.Message, channel: fluxer.Channel | None):
        if channel is None:
            channel = await bot.fetch_channel(str(message.channel_id))

        perms = await compute_permissions(await get_member(channel.guild_id, bot, bot.user.id), bot, channel)
        required = {
            "Manage Webhooks": 1 << 29,
            "View Channel": 1 << 10,
            "Send Message": 1 << 11,
            "Manage Messages": 1 << 13,
            "Embed Links": 1 << 14,
            "Attach Files": 1 << 15,
            "Read Message History": 1 << 16,
            "Use External Emojis": 1 << 18,
            "Use External Stickers": 1 << 37,
            "Add Reactions": 1 << 6,
            "Bypass Slowmode": 1 << 52,
            "Manage Roles": 1 << 28
        }
        passed = []
        denied = []
        for name, number in required.items():
            if perms & number == number:
                passed.append(name)
            else:
                denied.append(name)
        await response.respond(message, "", [fluxer.Embed(
            "Permissions",
            f"**Permissions granted**: {', '.join(passed) if passed else '*None*'}.\n**Permissions missing**: {', '.join(denied) if denied else '*None*'}."
        )])


    @register_command([optional_type(str)], bot, "stats", """
    Gets global statistics about the bot.
    If provided, `stat` will return only that specific statistic.
    """, "stats [stat]", ["stats", "stats proxy_uses"], "bot", ["stat"])
    async def stats(message: fluxer.Message, stat: str | None):
        all_stats: dict[str, Any] = await Database.instance.get_global_stats()
        all_stats.update({
            "uptime": datetime.now() - start_time,
            "guilds": len(bot.guilds),
            "cache_hits": CacheStatus.instance.hits,
            "cache_misses": CacheStatus.instance.misses,
            "commands": commands.session_command_usages
        })
        if message.author.id in Config.instance.devs:
            all_stats.update(CacheStatus.instance.miss_cause)
        all_stats["uptime"] = datetime.now() - start_time
        mapping = {
            "proxy_uses": ("Total proxy uses", lambda n: int(n)),
            "guilds": ("Total community count", lambda n: int(n)),
            "total_proxies": ("Total registered proxies", lambda n: int(n)),
            "uptime": ("Uptime", lambda td: td),
            "cache_hits": ("Cache hits", lambda n: int(n)),
            "cache_misses": ("Cache misses", lambda n: int(n)),
            "commands": ("Session command invocations", lambda n: int(n)),
            "version": ("Database version", lambda n: int(n))
        }
        if stat:
            if stat in all_stats:
                m = mapping.get(stat, (stat, lambda n: str(n)))
                await message.reply("", embeds=[fluxer.Embed(
                    f"{Config.instance.name} Statistics",
                    f"**{m[0]}** (`{stat}`): {m[1](all_stats[stat])}"
                ).to_dict()])
            else:
                await response.respond(message, f"Error! `{stat}` is not recognized as a tracked statistic!")
        else:
            await message.reply("", embeds=[fluxer.Embed(
                f"{Config.instance.name} Statistics",
                "\n".join(f"**{(m := mapping.get(stat, (stat, lambda n: str(n))))[0]}** (`{stat}`): {m[1](all_stats[stat])}" for stat in all_stats)
            ).to_dict()])


    '''
    @register_command([], bot, "donate", """
    Donate to support the bot's development!
    """, "donate", ["donate"], "bot")
    async def donate(message: fluxer.Message):
        await response.respond(message, "", [fluxer.Embed(
            "Support the Bot!",
            f"I have a donation link now! You can donate to me to support {Config.instance.name}'s development! [{Config.instance.donation}]({Config.instance.donation})."
        )])
    '''