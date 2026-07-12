from ..generic import make_command, Argument, make_command_group, get_commands, get_command_groups, CommandGroup
from ..generic.strategies import OneOf, OptionList, Optional, List, RangeStrategy, IntegerStrategy
from ..specific import ProxyStrategy
from ...backend.config import Config

def setup():
    spotlight_group = make_command_group(
        "spotlight_commands",
        "Spotlight Commands",
        "Commands that configures the spotlight list."
    )

    spotlight_group.append(make_command(
        {
            "spotlight list": [
                "spot list", "front list"
            ]
        },
        "Shows your current spotlight.",
        """
        Shows your current spotlight.
        """,
        []
    ))

    spotlight_group.append(make_command(
        {
            "spotlight set": [
                "spot set", "front set", "switch"
            ]
        },
        "Sets your current spotlight.",
        """
        Sets your current spotlight.
        If no proxies are provided, the spotlight will be empty.
        """,
        [
            Argument(
                "proxies",
                Optional(
                    List(
                        ProxyStrategy(),
                        fatal=True
                    ),
                    []
                )
            )
        ]
    ))

    spotlight_group.append(make_command(
        {
            "spotlight add": [
                "spot add", "front add", "spot push"
            ]
        },
        "Adds a proxy to your current spotlight.",
        """
        Adds a proxy to your current spotlight.
        """,
        [
            Argument(
                "proxy",
                ProxyStrategy()
            )
        ]
    ))

    spotlight_group.append(make_command(
        {
            "spotlight clear": [
                "spot clear", "front clear", "switch out"
            ]
        },
        "Clears your current spotlight list.",
        """
        Clears your current spotlight list.
        """,
        []
    ))

    spotlight_group.append(make_command(
        {
            "spotlight pop": [
                "spot pop", "front pop"
            ]
        },
        "Removes the last entered spotlight proxy.",
        """
        Removes the last entered spotlight proxy.
        """,
        []
    ))

    spotlight_group.append(make_command(
        {
            "spotlight insert": [
                "spot insert", "front insert"
            ]
        },
        "Inserts a proxy into the current spotlight.",
        """
        Inserts a proxy into the current spotlight.
        If not provided, the default index is the first spot.
        """,
        [
            Argument(
                "proxy",
                ProxyStrategy()
            ),
            Argument(
                "index",
                Optional(
                    IntegerStrategy(),
                    1
                )
            )
        ]
    ))
