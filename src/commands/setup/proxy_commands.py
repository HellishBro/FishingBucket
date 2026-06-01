from ..generic import make_command_group, make_command, Argument
from ..specific import TemplateStrategy


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
