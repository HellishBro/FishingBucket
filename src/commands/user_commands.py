import fluxer
from fluxer.models import RawReactionActionEvent

from . import register_group, register_command
from .. import response
from ..backend.database import Database
from ..backend.models import alternative, one_or_more
from ..interaction import Interactions, Interaction, remove_reaction

def setup(bot: fluxer.Bot):
    register_group("user", "User Commands", "Miscellaneous commands related to account, user, and privacy settings.")

    @register_command([fluxer.User], bot, "link", """
    Links another account with yours.
    The linked account and yours will share the same proxies, groups, and settings.
    This will essentially forward all command usage done on that account to your current account.
    """, "link <user>", ["link @BobAlt#2331"], "user")
    async def link(message: fluxer.Message, user: fluxer.User):
        if message.author.id == user.id:
            await response.respond(message, "You cannot link yourself to yourself!")
            return
        if user.bot:
            await response.respond(message, "You cannot link yourself to a bot!")
            return
        owner = await Database.instance.get_user_id(user.id)
        if owner == message.author.id:
            await response.respond(message, "That account is already linked to you!")
            return
        if owner != user.id:
            await response.respond(message, "That account is already linked to another account!")
            return

        m = await response.respond(message, "React to this message from the other account to link accounts!")
        await m.add_reaction("✅")

        async def cb(event: RawReactionActionEvent):
            if event.emoji.name == "✅":
                await Database.instance.link_accounts(await Database.instance.get_user_id(message.author.id), user.id)
                await response.respond(message, f"Successfully linked <@{user.id}> with your account!")

        Interactions.instance.add_interaction(m.id, Interaction(user.id, cb, 60))

        if await Interactions.instance.wait_claim_after(60, m.id, user.id):
            await m.edit("Account link confirmation expired!")
            await remove_reaction(m, "✅")

    @register_command([], bot, "unlink", """
    Unlinks this account with the linked account.
    This command must be ran on the linked account, not the parent account.
    """, "unlink", ["unlink"], "user")
    async def unlink(message: fluxer.Message):
        parent = await Database.instance.get_user_id(message.author.id)
        if parent == message.author.id:
            await response.respond(message, "This account does not have a parent account!")
        else:
            await Database.instance.unlink_account(message.author.id)
            await response.respond(message, f"Successfully unlinked this account with <@{parent}>!")

    @register_command(
        [],
        bot, "privacy", """
        Lists your privacy settings.
        The options for privacy are:
        - Proxy and group description (`description`)
        - Proxy triggers (`triggers`)
        - Proxy and group metadata (`metadata`)
        - Proxy groups (`groups`)
        - Or, simply viewing your proxies and groups at all (`list`)
        
        Using proxy or group list commands in bot DMs will show private fields.
        """, 'privacy', ["privacy"], "user"
    )
    async def privacy_list(message: fluxer.Message):
        preferences = await Database.instance.get_user_preferences(message.author.id)
        pref_dict = {
            "private_description": False,
            "private_trigger": False,
            "private_metadata": False,
            "private_group": False,
            "private_list": False
        }
        for k, v in preferences._asdict().items():
            if k in pref_dict:
                pref_dict[k] = v

        m = {
            "private_description": "description",
            "private_trigger": "triggers",
            "private_metadata": "metadata",
            "private_group": "groups",
            "private_list": "list"
        }

        public_options = [m[p] for p, v in pref_dict.items() if not v]
        private_options = [m[p] for p, v in pref_dict.items() if v]
        await response.respond(message, "", [fluxer.Embed(
            "Privacy List",
            f"Currently, your privacy settings are:\n\n**Public**: {', '.join(public_options) if public_options else '*N/A*'}\n**Private**: {', '.join(private_options) if private_options else '*N/A*'}"
        )])

    @register_command(
        [alternative("public", "private"), alternative("all", one_or_more(alternative("description", "triggers", "metadata", "groups", "list")))],
        bot, "privacy set", """
        Sets your privacy settings.
        `mode` will set the provided options public/private.
        The support options for privacy are:
        - Proxy and group description (`description`)
        - Proxy triggers (`triggers`)
        - Proxy and group metadata (`metadata`)
        - Proxy groups (`groups`)
        - Or, simply viewing your proxies and groups at all (`list`)
        
        Using proxy or group list commands in bot DMs will show private fields.
        """, 'privacy set <"public" OR "private"> <option(s) OR "all">', [
            "privacy set public all",
            "privacy set private description triggers"
        ], "user"
    )
    async def privacy_set(message: fluxer.Message, mode: str, options: list[str] | str):
        if options == "all":
            options = ["description", "triggers", "metadata", "groups", "list"]

        m = {
            "description": "private_description",
            "triggers": "private_trigger",
            "metadata": "private_metadata",
            "groups": "private_group",
            "list": "private_list"
        }

        public = mode == "private"
        kwargs = {m[k]: public for k in options}

        await Database.instance.set_user_preferences(message.author.id, **kwargs)
        await response.respond(message, "", [fluxer.Embed(
            "Privacy Set!",
            f"Successfully set the following privacy options to **{mode}**: {", ".join(options)}."
        )])
