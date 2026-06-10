import asyncio
import time
from typing import Literal

from lorem_text import lorem

from .generic import hook_command
from .specific import get_uid
from ..backend.config import Config
from ..backend.database import Database
from ..backend.models import Platform
from ..interaction import Interactions, Interaction
from ..service import Context, Embed, ReactionActionEvent
from ..service.server import PLATFORM_TO_SERVER

account_links: dict[str, tuple[int, tuple[int, Platform], float, str]] = {} # link code => (uid, (user_id, platform), timestamp, name)
account_links_initiated_accounts: dict[tuple[int, Platform], float] = {} # (user_id, platform) => timestamp


def setup():
    @hook_command("privacy list")
    async def _(context: Context):
        uid = await get_uid(context)
        preferences = await Database.instance.get_user_preferences(uid)
        pref_dict = {
            "private_description": False,
            "private_trigger": False,
            "private_metadata": False,
            "private_group": False,
            "private_list": False,
            "private_forms": False
        }
        for k, v in preferences._asdict().items():
            if k in pref_dict:
                pref_dict[k] = v

        m = {
            "private_description": "description",
            "private_trigger": "triggers",
            "private_metadata": "metadata",
            "private_group": "groups",
            "private_list": "list",
            "private_forms": "forms"
        }

        public_options = [m[p] for p, v in pref_dict.items() if not v]
        private_options = [m[p] for p, v in pref_dict.items() if v]
        await context.reply("", [Embed(
            "Privacy List",
            f"Currently, your privacy settings are:\n\n**Public**: {', '.join(public_options) if public_options else '*N/A*'}\n**Private**: {', '.join(private_options) if private_options else '*N/A*'}"
        )])


    @hook_command("privacy set")
    async def _(context: Context, status: Literal["private"] | Literal["public"], options: list[str] | Literal["all"]):
        if options == "all":
            options = ["description", "triggers", "metadata", "groups", "list", "forms"]

        m = {
            "description": "private_description",
            "triggers": "private_trigger",
            "metadata": "private_metadata",
            "groups": "private_group",
            "list": "private_list",
            "forms": "private_forms"
        }

        public = status == "private"
        kwargs = {m[k]: public for k in options}

        await Database.instance.set_user_preferences(await get_uid(context), **kwargs)
        await context.reply("", [Embed(
            "Privacy Set!",
            f"Successfully set the following privacy options to **{status}**: {", ".join(options)}."
        )])


    @hook_command("link initiate")
    async def _(context: Context):
        key = (context.author.id, context.platform)
        now = time.time()
        if key in account_links_initiated_accounts and now - account_links_initiated_accounts[key] <= 120:
            await context.reply(f"Error: you already have an outgoing link code. Redeem it or let it expire before creating a new one.")
            return

        uid = await get_uid(context)

        channel = await context.author.get_dm()

        new_code = lorem.words(10)
        account_links_initiated_accounts[key] = now
        account_links[new_code] = uid, key, now, "@" + context.author.full_tag

        await channel.send(f"Execute this entire command from the account that you want to link from to complete the process!")
        await channel.send(f"{Config.prefix()}link code {new_code}")

        this_channel = await context.get_channel(context.message.channel_id)
        if not this_channel.dm:
            await context.reply("I've sent you instructions in your DM!")

        await asyncio.sleep(120)

        if key in account_links_initiated_accounts:
            await channel.send(f"Account link code expired.")
            account_links_initiated_accounts.pop(key)
            account_links.pop(new_code)


    @hook_command("link code")
    async def _(context: Context, code: str):
        if code not in account_links:
            await context.reply("Error: that is not a valid link code. Did you copy the entire command correctly?")
            return

        uid, parent_user, timestamp, name = account_links[code]

        if parent_user == (context.author.id, context.platform):
            await context.reply("Error: you cannot link yourself to yourself.")
            return

        self = await Database.instance.get_user_id(context.author.id, context.platform, False)
        if uid == self:
            await context.reply("Error: you are already linked with that account.")
            return
        if self != -1:
            await context.reply("Error: you already have an account. Please delete your account or unlink to link.")
            return

        m = await context.reply(f"Are you sure you want to link with **{name}**? React with :white_check_mark: to confirm.")
        await m.message.add_reaction("✅")

        async def cb(event: ReactionActionEvent) -> bool:
            if event.emoji == "✅":
                await Database.instance.link_accounts(uid, context.author.id, context.platform)
                await context.reply("Successfully linked your account!")

                account_links.pop(code)
                account_links_initiated_accounts.pop(parent_user)
                return True
            return False

        now = time.time()
        to = 120 - (now - timestamp)
        Interactions.instance.add_interaction(m, Interaction(context.author.id, cb, to))

        if await Interactions.instance.wait_claim_after(to, m.id, context.platform):
            await m.message.edit("Account linking expired.")
            await m.message.remove_reaction("✅")


    @hook_command("link list")
    async def _(context: Context):
        uid = await get_uid(context)

        accounts = await Database.instance.get_accounts(uid)
        accounts_str = []

        for account in accounts:
            account_id, account_type = account
            user = await PLATFORM_TO_SERVER[account_type].get_bot().get_user(account_id)
            string = f"- {account_type.name}: {user.display_name} (@{user.full_tag})"
            if account == (context.author.id, context.platform):
                string += " (current)"

            accounts_str.append(string)

        channel = await context.author.get_dm()
        await channel.send("", [Embed(
            "Linked Accounts",
            "Your linked accounts:\n" + "\n".join(accounts_str)
        )])

        this_channel = await context.get_channel(context.message.channel_id)
        if not this_channel.dm:
            await context.reply("I've sent your linked account information in your DM!")


    @hook_command("unlink")
    async def _(context: Context):
        uid = await get_uid(context)
        linkers = await Database.instance.get_accounts(uid)
        if len(linkers) == 1:
            await context.reply("Error: you cannot unlink the only remaining user.")
            return

        m = await context.reply("Are you sure you want to unlink yourself? React with :white_check_mark: to confirm. This message will expire in 20 seconds.")
        await m.message.add_reaction("✅")

        async def cb(event: ReactionActionEvent) -> bool:
            if event.emoji == "✅":
                await Database.instance.unlink_account(context.author.id, context.platform)
                await context.reply("Successfully unlinked your account!")
                return True
            return False

        Interactions.instance.add_interaction(m, Interaction(context.author.id, cb, 20))

        if await Interactions.instance.wait_claim_after(20, m.id, context.platform):
            await m.message.edit("Account unlinking process expired.")
            await m.message.remove_reaction("✅")



    @hook_command("account delete")
    async def _(context: Context):
        owner = await get_uid(context)

        m = await context.reply(f"> [!CAUTION]\n> Are you sure you want to **delete everything**? React to the :white_check_mark: to confirm. This message will expire in 10 seconds.")
        await m.message.add_reaction("✅")

        async def cb(event: ReactionActionEvent):
            if event.emoji == "✅":
                await Database.instance.account_reset(owner)
                await context.reply(f"Successfully deleted your account!")

        Interactions.instance.add_interaction(m, Interaction(context.author.id, cb, 10))

        if await Interactions.instance.wait_claim_after(10, m.id, context.platform):
            await m.message.edit("Account reset confirmation expired!")
            await m.message.remove_reaction("✅")
