from ..commands.generic import make_command, Argument, make_command_group, get_commands, get_command_groups
from ..commands.generic.strategies import OneOf, OptionList, Optional


def setup():
    bot_group = make_command_group(
        "bot",
        "Bot Commands",
        "Commands related to the bot itself."
    )

    bot_group.append(
        make_command(
            "ping",
            "Gets the bot's latency.",
            "Gets the bot's latency.",
            []
        )
    )

    bot_group.append(
        make_command(
            "invite",
            "Invite me to your community!",
            "Invite me to your community, or join the bot's support community!",
            []
        )
    )

    bot_group.append(
        make_command(
            {
                "stats": ["botinfo", "info"]
            },
            "Get global statistics about the bot.",
            """
            Get global statistics about the bot.
            If provided, `stat` will return only that specific statistic.
            """,
            [
                Argument(
                    "stat",
                    Optional(
                        OptionList(
                            None,
                            [
                                "proxy_uses",
                                "guilds",
                                "total_proxies",
                                "uptime",
                                "cache_efficiency",
                                "command_count",
                                "invocations",
                                "version"
                            ]
                        ),
                        None
                    )
                )
            ]
        )
    )

    bot_group.append(
        make_command(
            {
                "help": ["h", "?", ""]
            },
            "Provides information about this bot or about a command.",
            """
            Provides information about this bot or about a command or command category.
            If a command is provided, it will show the command description, usage, as well as examples.
            If a category is provided, it will then show the commands on that category.
            """,
            [
                Argument(
                    "topic",
                    Optional(
                        OneOf(
                            OptionList(
                                "command",
                                {
                                    cmd.canonical_name: cmd.aliases
                                    for cmd in get_commands().values()
                                } | {
                                    "help": ["h", "?"]
                                },
                                True
                            ),
                            OptionList(
                                "category",
                                [
                                    group.canonical_name
                                    for group in get_command_groups().values()
                                ],
                                True
                            )
                        ),
                        None
                    )
                )
            ]
        )
    )