from typing import Literal, Tuple

from .generic import hook_command
from .specific import get_uid
from .utils import example_trigger_text
from ..backend.database import Database
from ..backend.models import Proxy
from ..backend.template_utils import Template
from ..backend.utils import normalize_emojis
from ..interaction import Interactions, Interaction
from ..service import Context, ReactionActionEvent, Embed


def setup():
    @hook_command("set avatar")
    async def _(context: Context, proxy: Proxy, url: str | None):
        if not context.message.attachments:
            avatar_url = url or Proxy.random_avatar()
        else:
            avatar_url = context.message.attachments[0].url

        await Database.instance.update_avatar(proxy.id, avatar_url)
        embed = Embed(
            "Proxy Updated!",
            f"The avatar for **{proxy.name}** has been updated!",
            thumbnail_url=avatar_url
        )
        await context.reply("", [embed])


    @hook_command("set triggers")
    async def _(context: Context, proxy: Proxy, mode: Literal["set"] | Literal["add"] | Literal["remove"], trigger: Template | None):
        if mode == "add" and trigger is None:
            await context.reply("Error: 'add' mode must have a trigger to add.")
            return

        new_triggers = proxy.triggers or []
        if mode == "set":
            if trigger is None: new_triggers = []
            else: new_triggers = [trigger.string]
        elif mode == "remove":
            if trigger is None: new_triggers = []
            if trigger in proxy.triggers: new_triggers.remove(trigger.string)
        elif mode == "add":
            new_triggers.append(trigger.string)
            new_triggers = [*set(new_triggers)]

        await Database.instance.update_trigger(proxy.id, new_triggers)

        if new_triggers:
            embed = Embed(
                "Proxy Updated!",
                f"The triggers for **{proxy.name}** has been changed to {', '.join('`' + trigger + '`' for trigger in new_triggers)}!\nSay hello with it by typing `{example_trigger_text(trigger)}`{' or by other triggers' if len(new_triggers) != 1 else ''}!"
            )
        else:
            embed = Embed(
                "Proxy Updated!",
                f"The triggers for **{proxy.name}** has been removed! You won't be able to use this proxy via a trigger anymore."
            )

        await context.reply("", [embed])


    @hook_command("set name")
    async def _(context: Context, proxy: Proxy, new_name: str):
        old_name = proxy.name
        new_name = normalize_emojis(new_name)
        await Database.instance.update_name(proxy.id, new_name)
        embed = Embed(
            "Proxy Updated!",
            f"The name for the previous *{old_name}* has been changed to **{new_name}**!"
        )
        await context.reply("", [embed])


    @hook_command("set nickname")
    async def _(context: Context, proxy: Proxy, new_nickname: str | None):
        old_name = proxy.name
        new_nickname = normalize_emojis(new_nickname)
        await Database.instance.update_nickname(proxy.id, new_nickname)
        embed = Embed(
            "Proxy Updated!",
            f"The nickname for *{old_name}* has been " + (
                f"changed to **{new_nickname}**!" if new_nickname else "cleared!")
        )
        await context.reply("", [embed])


    @hook_command("set pronouns")
    async def _(context: Context, proxy: Proxy, new_pronouns: str | None):
        await Database.instance.update_pronouns(proxy.id, new_pronouns)
        if new_pronouns:
            embed = Embed(
                "Proxy Updated!",
                f"The pronouns for **{proxy.name}** has been changed to **{new_pronouns}**!"
            )
        else:
            embed = Embed(
                "Proxy Updated!",
                f"The pronouns for **{proxy.name}** has been reset!"
            )
        await context.reply("", [embed])


    @hook_command("set description")
    async def _(context: Context, proxy: Proxy, new_description: str | None):
        if new_description is None:
            new_description = ""

        await Database.instance.update_description(proxy.id, new_description)
        if new_description:
            embed = Embed(
                "Proxy Updated!",
                f"The description for {proxy.name} has been changed! New description:\n" +
                "\n".join("> " + line for line in new_description.split("\n"))
            )
        else:
            embed = Embed(
                "Proxy Updated!",
                f"The description for {proxy.name} has been cleared!"
            )
        await context.reply("", [embed])


    @hook_command("set forms")
    async def _(context: Context, proxy: Proxy, mode: Literal["set"] | Literal["add"] | Literal["remove"], form: Tuple[str, str | None] | None):
        if mode == "add" and form is None:
            await context.reply("Error: 'add' mode must have a form to add.")
            return

        avatar_url = None
        if mode in ("add", "set"):
            if form[1] is None:
                if not context.message.attachments:
                    avatar_url = form[1] or Proxy.random_avatar()
                else:
                    avatar_url = context.message.attachments[0].url

        forms = proxy.forms
        curr_form = proxy.current_form

        if mode in ("add", "set"):
            if form:
                forms[form[0]] = avatar_url
            else:
                forms = {}
                curr_form = None
        elif mode == "remove":
            if form:
                if form[0] in forms:
                    forms.pop(form[0])
                    if curr_form == form[0]:
                        curr_form = None
            else:
                forms = {}

        await Database.instance.update_forms(proxy.id, forms)
        await Database.instance.update_current_form(proxy.id, curr_form)

        forms_text = []
        for fname, furl in forms.items():
            text = f"- {fname}: [avatar]({furl})"
            if curr_form == fname:
                text += " (current)"
            forms_text.append(text)
        forms_text = "\n".join(forms_text) if forms_text else "No forms!"

        embed = Embed(
            "Proxy Updated!",
            f"The forms for **{proxy.name}** has been changed! Proxy forms:\n{forms_text}"
        )
        await context.reply("", [embed])


    @hook_command("set current form")
    async def _(context: Context, proxy: Proxy, form: str | None):
        if form is None:
            await Database.instance.update_current_form(proxy.id, None)
            await context.reply("", [Embed(
                "Proxy Updated!",
                f"The current form for **{proxy.effective_name}** has been reset."
            )])
            return

        if form in proxy.forms:
            await Database.instance.update_current_form(proxy.id, form)
            await context.reply("", [Embed(
                "Proxy Updated!",
                f"The current form for **{proxy.effective_name}** has been changed to `{form}`."
            )])
        else:
            await context.reply(f"Error: **{proxy.effective_name}** does not have the form `{form}`!")


    @hook_command("remove")
    async def _(context: Context, proxy: Proxy):
        m = await context.reply(f"> [!WARNING]\n> Are you sure you want to remove **{proxy.name}**? React to the :white_check_mark: to confirm. This message will expire in 30 seconds.")
        await m.message.add_reaction("✅")

        async def cb(event: ReactionActionEvent) -> bool:
            if event.emoji == "✅":
                await Database.instance.delete_proxy(proxy.id)
                await m.reply(f"Successfully removed **{proxy.name}**!")
                return True
            return False

        Interactions.instance.add_interaction(m, Interaction(context.author.id, cb))

        if await Interactions.instance.wait_claim_after(30, m.id, m.platform):
            await m.message.edit("Proxy remove confirmation expired.")
            await m.message.remove_reaction("✅")


    @hook_command("nuke")
    async def _(context: Context):
        owner = await get_uid(context)
        proxies = await Database.instance.get_user_proxies(owner)
        groups = await Database.instance.get_user_groups(owner)

        if not proxies and not groups:
            await context.reply("You have no proxies nor proxy groups to delete!")
            return

        m = await context.reply(f"> [!CAUTION]\n> Are you sure you want to nuke **all of your {len(proxies)} proxies and {len(groups)} groups**? React to the :white_check_mark: to confirm. This message will expire in 10 seconds.")
        await m.message.add_reaction("✅")

        async def cb(event: ReactionActionEvent) -> bool:
            if event.emoji == "✅":
                await Database.instance.delete_data(owner)
                await m.reply(f"Successfully nuked your proxies!")
                return True
            return False

        Interactions.instance.add_interaction(m, Interaction(context.author.id, cb, 10))

        if await Interactions.instance.wait_claim_after(10, m.id, context.platform):
            await m.message.edit("Proxy nuke confirmation expired!")
            await m.message.remove_reaction("✅")
