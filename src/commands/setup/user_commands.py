from ..generic import make_command_group, make_command, Argument
from ..generic.strategies import OneOf, Literal, List, OptionList, Optional, StringStrategy


def setup():
    user_commands = make_command_group(
        "user_commands",
        "User Commands",
        "Commands related to account, user, and privacy settings."
    )

    user_commands.append(
        make_command(
            {
                "privacy list": [
                    "privacy l"
                ]
            },
            "Lists your privacy settings.",
            """
            Lists your privacy settings.
            The options for privacy are:
            - Proxy and group description (`description`)
            - Proxy triggers (`triggers`)
            - Proxy and group metadata (`metadata`)
            - Proxy groups (`groups`)
            - Proxy forms (`forms`)
            - Or, simply viewing your proxies and groups at all (`list`)
            
            Using proxy or group list commands in bot DMs will show private fields.
            """,
            []
        )
    )

    user_commands.append(
        make_command(
            {
                "privacy set": [
                    "privacy set",
                    "privacy ="
                ]
            },
            "Sets your privacy settings.",
            """
            Sets your privacy settings.
            `status` will set the provided options public/private.
            The support options for privacy are:
            - Proxy and group description (`description`)
            - Proxy triggers (`triggers`)
            - Proxy and group metadata (`metadata`)
            - Proxy groups (`groups`)
            - Proxy forms (`forms`)
            - Or, simply viewing your proxies and groups at all (`list`)
            
            Using proxy or group list commands in bot DMs will show private fields.
            """,
            [
                Argument(
                    "status",
                    OptionList(
                        None,
                        [
                            "public",
                            "private"
                        ]
                    )
                ),
                Argument(
                    "options",
                    OneOf(
                        Literal("all"),
                        List(
                            OptionList(
                                "setting",
                                [
                                    "description",
                                    "triggers",
                                    "metadata",
                                    "groups",
                                    "forms",
                                    "list"
                                ]
                            )
                        )
                    )
                )
            ]
        )
    )

    user_commands.append(
        make_command(
            "link initiate",
            "Initiates account linking procedure.",
            """
            Initiates account linking procedure.
            The linked account and yours will share the same proxies, groups, and settings.
            This command will generate a link code that is used to link another account with yours.
            """,
            []
        )
    )

    user_commands.append(
        make_command(
            "link code",
            "Finishes the account linking procedure.",
            """
            Finishes the account linking procedure.
            Linked accounts will share the same proxies, groups, and settings.
            """,
            [
                Argument(
                    "code",
                    str,
                    lambda: "<key>"
                )
            ]
        )
    )

    user_commands.append(
        make_command(
            "link list",
            "Lists all of your linked accounts.",
            """
            Lists all of your linked accounts.
            """,
            []
        )
    )

    user_commands.append(
        make_command(
            "unlink",
            "Unlinks your account.",
            """
            Unlinks your account.
            You cannot remove the last linked account.
            """,
            []
        )
    )

    user_commands.append(
        make_command(
            "account delete",
            "Deletes every information related to your account.",
            """
            Deletes every information related to your account. This action is **irreversible**!
            Your account will cease to exist, and every proxy, group, user setting, connected account, and others will cease to exist with it!
            """,
            []
        )
    )
