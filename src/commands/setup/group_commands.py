from ..generic import make_command_group, make_command, Argument
from ..generic.strategies import Optional, StringStrategy, OneOf, Sequence, Literal, List
from ..specific import UnknownPageNumber, ProxyGroupStrategy, ProxyStrategy, TemplateStrategy


def setup():
    group_commands = make_command_group(
        "group_commands",
        "Group Commands",
        "Commands related to creating and adjusting groups."
    )

    group_commands.append(
        make_command(
            {
                "group register": [
                    "g r",
                    "g new",
                    "group new"
                ]
            },
            "Creates a new group.",
            """
            Creates a new group. This will also create your account.
            Groups help you organize different proxies or other groups that are related in some way.
            """,
            [
                Argument(
                    "name",
                    str,
                    lambda: "\"My Group's Name\""
                ),
                Argument(
                    "description",
                    Optional(
                        StringStrategy("MEDIUM"),
                        ""
                    )
                )
            ]
        )
    )

    group_commands.append(
        make_command(
            {
                "group list": [
                    "g l"
                ]
            },
            "Lists your proxy groups.",
            """
            Lists your proxy groups.
            This will only list the groups themselves, not the items in the groups.
            
            If `page` is provided, it will display the groups on that page number.
            If `detailed` is provided, it will ignore your privacy preferences and display everything. This is automatically true in DMs.
            As of now, this command will not be able to inspect another user's groups.
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

    group_commands.append(
        make_command(
            {
                "group info": [
                    "g i"
                ]
            },
            "Shows you information about a group.",
            """
            Shows you information about a group that you own.
            If `detailed` is provided, it will ignore your privacy preferences and display everything. This is automatically true in DMs.
            As of now, this command will not be able to inspect another user's groups.
            """,
            [
                Argument(
                    "group",
                    ProxyGroupStrategy()
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

    group_commands.append(
        make_command(
            {
                "group members": [
                    "g m",
                    "g members",
                    "members"
                ]
            },
            "Shows you the members belonging in a group.",
            """
            Shows you the members belonging in a group that you own.
            If `detailed` is provided, it will ignore your privacy preferences and display everything. This is automatically true in DMs.
            As of now, this command will not be able to inspect another user's groups.
            """,
            [
                Argument(
                    "group",
                    ProxyGroupStrategy()
                ),
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

    group_commands.append(
        make_command(
            {
                "group name": [
                    "g name"
                ]
            },
            "Updates a group's name.",
            """
            Updates a group's name.
            """,
            [
                Argument(
                    "group",
                    ProxyGroupStrategy()
                ),
                Argument(
                    "name",
                    str,
                    lambda: "\"My Group's Name\""
                )
            ]
        )
    )

    group_commands.append(
        make_command(
            {
                "group tag": [
                    "g tag"
                ]
            },
            "Updates a group's tag.",
            """
            Updates a group's tag.
            A tag appears in the proxy name of that group when the proxy is used.
            A proxy tag must contain the literal `{}` as the placeholder for the proxy's name.
            If not provided, the proxy tag will be cleared.
            """,
            [
                Argument(
                    "group",
                    ProxyGroupStrategy()
                ),
                Argument(
                    "tag",
                    Optional(
                        TemplateStrategy([
                            "name",
                            "proxy",
                            "group"
                        ]),
                        None
                    )
                )
            ]
        )
    )

    group_commands.append(
        make_command(
            {
                "group description": [
                    "group desc",
                    "g description",
                    "g desc"
                ]
            },
            "Updates a group's description.",
            """
            Updates a group's description.
            """,
            [
                Argument(
                    "group",
                    ProxyGroupStrategy()
                ),
                Argument(
                    "description",
                    Optional(
                        StringStrategy("MEDIUM"),
                        ""
                    )
                )
            ]
        )
    )

    group_commands.append(
        make_command(
            {
                "group add": [
                    "g add",
                    "g +"
                ]
            },
            "Adds items to a group.",
            """
            Adds items to a group.
            Each item can only belong in one group.
            A group can contain both proxies and other groups.
            """,
            [
                Argument(
                    "to",
                    ProxyGroupStrategy()
                ),
                Argument(
                    "items",
                    OneOf(
                        Sequence(
                            Argument(
                                "type",
                                Literal("proxies")
                            ),
                            Argument(
                                "proxies",
                                List(
                                    ProxyStrategy(),
                                    1
                                )
                            ),
                            discriminated_fields=1
                        ),
                        Sequence(
                            Argument(
                                "type",
                                Literal("groups")
                            ),
                            Argument(
                                "groups",
                                List(
                                    ProxyGroupStrategy(),
                                    1
                                )
                            ),
                            discriminated_fields=1
                        )
                    )
                )
            ]
        )
    )

    group_commands.append(
        make_command(
            {
                "group remove": [
                    "g remove",
                    "g rem",
                    "group rem",
                    "g rm",
                    "group rm",
                    "g -"
                ]
            },
            "Removes items from a group.",
            """
            Removes items from a group.
            """,
            [
                Argument(
                    "from",
                    ProxyGroupStrategy()
                ),
                Argument(
                    "items",
                    OneOf(
                        Sequence(
                            Argument(
                                "type",
                                Literal("proxies")
                            ),
                            Argument(
                                "proxies",
                                List(
                                    ProxyStrategy(),
                                    1
                                )
                            ),
                            discriminated_fields=1
                        ),
                        Sequence(
                            Argument(
                                "type",
                                Literal("groups")
                            ),
                            Argument(
                                "groups",
                                List(
                                    ProxyGroupStrategy(),
                                    1
                                )
                            ),
                            discriminated_fields=1
                        )
                    )
                )
            ]
        )
    )

    group_commands.append(
        make_command(
            {
                "group delete": [
                    "group del",
                    "g del",
                    "g delete"
                ]
            },
            "Deletes a group that you own.",
            """
            Deletes a group that you own.
            All items within the group will be automatically ungrouped.
            """,
            [
                Argument(
                    "group",
                    ProxyGroupStrategy()
                )
            ]
        )
    )
