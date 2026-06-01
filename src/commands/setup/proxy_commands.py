import random

from ..generic import make_command_group, make_command, Argument
from ..generic.strategies import Optional
from ..specific import TemplateStrategy, UnknownPageNumber


def setup():
    proxy_commands = make_command_group(
        "proxy_commands",
        "Proxy Commands",
        "Commands related to creating, getting, and using proxies."
    )

    proxy_commands.append(
        make_command(
            {
                "register": [
                    "r"
                ]
            },
            "Registers a proxy to be used.",
            """
            Registers a proxy to be used. This will also create your account.
            The trigger is a string that contains `{}` somewhere.
            Proxy avatar can be set by attaching an image to the message.
            """,
            [
                Argument(
                    "name",
                    str,
                    lambda: "\"My Proxy's Name\""
                ),
                Argument(
                    "trigger",
                    TemplateStrategy([
                        "text"
                    ])
                )
            ]
        )
    )

    proxy_commands.append(
        make_command(
            {
                "list": [
                    "l"
                ]
            },
            "Lists your registered proxies.",
            """
            Lists your registered proxies.
            If `page` is provided, it will display the proxies on that page number.
            If `detailed` is provided, it will ignore your privacy preferences and display everything. This is automatically true in DMs.
            As of now, this command will not be able to inspect another user's proxies.
            """,
            [
                Argument(
                    "page",
                    Optional(
                        UnknownPageNumber(),
                        0
                    )
                ),
                Argument(
                    "detailed",
                    Optional(
                        bool,
                        False
                    )
                )
            ]
        )
    )

    proxy_commands.append(
        make_command(
            {
                "find": [
                    "f"
                ]
            },
            "Finds all of your proxies that matches a certain name.",
            """
            Finds all of your proxies that matches a certain name.
            The first result will be chosen if you use the name as an argument to `proxy` type parameters.
            This will also list some issues that might give you an error if the name is used.
            """,
            [
                Argument(
                    "name",
                    str,
                    lambda: random.choice([
                        "\"My Proxy's Name\"",
                        "\"My Proyx's Naem\"",
                        "\"my poxy'sn ame\""
                    ])
                )
            ]
        )
    )
