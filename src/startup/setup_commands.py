from ..commands.generic import make_command, Argument
from ..commands.generic.strategies import OneOf, OptionList, Optional


def setup():
    make_command(
        {
            "help": [
                "h",
                "?",
                ""
            ]
        },
        "The help command",
        "This is a long description describing the help command",
        [
            Argument(
                "page or concept",
                Optional(
                    OneOf(
                        range(0, 4),
                        OptionList({
                            "help": [
                                "h"
                            ],
                            "commands": [
                                "cmd",
                                "cmds",
                                "command"
                            ]
                        })
                    ),
                    0
                )
            )
        ]
    )