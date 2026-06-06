import random

from ..generic import make_command_group, make_command, Argument
from ..generic.strategies import OptionList, Optional, WordStrategy


def dice_expression() -> str:
    def term() -> str:
        if random.randint(0, 1) == 0:
            a = random.randint(1, 4)
            b = random.choice([2, 4, 6, 8, 10, 20, 100])
            if a == 1: return f"d{b}"
            return f"{a}d{b}"
        return str(random.randint(1, 10))

    res = term()
    for _ in range(random.randint(0, 3)):
        res += " " + random.choice(["+", "-", "*"])
        res += term()

    return res


def setup():
    dice_commands = make_command_group(
        "dice_commands",
        "Dice Commands",
        "Commands related to the dice functionality of the bot."
    )

    dice_commands.append(
        make_command(
            "dice",
            "Roll dice or perform arithmetics.",
            """
            Roll dice or perform arithmetics.
            """,
            [
                Argument(
                    "expression",
                    str,
                    dice_expression
                )
            ]
        )
    )

    dice_commands.append(
        make_command(
            {
                "environment list": [
                    "environ list",
                    "env l"
                ]
            },
            "Gets all dice environment variables or functions.",
            """
            Gets all dice environment variables or functions.
            """,
            [
                Argument(
                    "target",
                    Optional(
                        OptionList(
                            None,
                            [
                                "user",
                                "community",
                                "global",
                                "all"
                            ],
                            True
                        ),
                        "all"
                    )
                ),
                Argument(
                    "object",
                    Optional(
                        OptionList(
                            None,
                            {
                                "variables": [
                                    "vars",
                                    "var",
                                    "variable"
                                ],
                                "functions": [
                                    "funcs",
                                    "func",
                                    "fns",
                                    "fn",
                                    "function"
                                ],
                                "all": []
                            },
                            True
                        ),
                        "all"
                    )
                )
            ]
        )
    )

    dice_commands.append(
        make_command(
            {
                "environment set": [
                    "environment add",
                    "environ add",
                    "environ set",
                    "env =",
                    "env +"
                ]
            },
            "Sets a variable or function to be used in dice expressions.",
            """
            Sets a variable or function to be used in dice expressions.
            You must have the **Manage Community** permission to set `target` to "community".
            """,
            [
                Argument(
                    "target",
                    OptionList(
                        None,
                        [
                            "user",
                            "community"
                        ]
                    )
                ),
                Argument(
                    "name",
                    WordStrategy()
                ),
                Argument(
                    "value",
                    str,
                    lambda: random.choice(["<expression>", "f(x)=<expression>"])
                )
            ]
        )
    )

    dice_commands.append(
        make_command(
            {
                "environment remove": [
                    "environ rm",
                    "environ rem",
                    "env -"
                ]
            },
            "Removes a dice variable or function.",
            """
            Removes a dice variable or function.
            You must have the **Manage Community** permission to set `target` to "community".
            """,
            [
                Argument(
                    "target",
                    OptionList(
                        None,
                        [
                            "user",
                            "community"
                        ]
                    )
                ),
                Argument(
                    "name",
                    WordStrategy()
                )
            ]
        )
    )
