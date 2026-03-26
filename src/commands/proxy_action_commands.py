import fluxer
from fluxer.models import RawReactionActionEvent

from .utils import proxy_username, ensure_own_proxy, valid_template, example_trigger_text
from .. import response
from ..backend.database import Database
from ..backend.utils import normalize_emojis
from ..commands import register_command, register_group
from ..interaction import Interaction, remove_reaction, Interactions
from ..backend.models import optional_type, one_or_more, Proxy, alternative


def setup(bot: fluxer.Bot):
    register_group("proxy_act", "Proxy Action Commands", "Commands that acts upon proxies.")

    @register_command([str], bot, "remove", """
    Removes a proxy that you own.
    Old messages will still be retained, but you will no longer be able to use this proxy.
    """, "remove <proxy>", ["remove 69ed73"], "proxy_act")
    async def remove(message: fluxer.Message, id_: str):
        proxy = await ensure_own_proxy(message, id_)
        if not proxy: return

        m = await response.respond(message,
                                   f"> [!WARNING]\n> Are you sure you want to remove **{proxy.name}**? React to the :white_check_mark: to confirm. This message will expire in 30 seconds.")
        await m.add_reaction("✅")
        msg_id = int(m.id)

        async def cb(event: RawReactionActionEvent):
            if event.emoji.name == "✅":
                await Database.instance.delete_proxy(proxy.id)
                await response.respond(message, f"Successfully removed **{proxy.name}**!")

        Interactions.instance.add_interaction(msg_id, Interaction(message.author.id, cb, 30))

        if await Interactions.instance.wait_claim_after(30, msg_id, message.author.id):
            await m.edit("Proxy remove confirmation expired!")
            await remove_reaction(m, "✅")

    @register_command([str, optional_type(str)], bot, "set avatar", """
    Updates a proxy's avatar.
    The new avatar could be attached to the message or passed down as a link in the `url` argument.
    """, "set avatar <proxy> [url]", ["set avatar 69ed73", "set avatar 69ed73 https://example.com/avatar.png"],
                      "proxy_act")
    async def change_avatar(message: fluxer.Message, id_: str, url: str | None):
        proxy = await ensure_own_proxy(message, id_)
        if not proxy: return

        if not message.attachments:
            avatar_url = url or Proxy.random_avatar()
        else:
            avatar_url = message.attachments[0].url

        await Database.instance.update_avatar(proxy.id, avatar_url)
        embed = fluxer.Embed(
            "Proxy Updated!",
            f"The avatar for **{proxy.name}** has been updated!"
        )
        embed.set_thumbnail(url=avatar_url)
        await response.respond(message, "", [embed])

    @register_command([str, alternative("set", "add", "remove"), optional_type(str)], bot, "set triggers", """
    Updates a proxy's triggers.
    The `new trigger` argument will be used to trigger your proxy after changing it.
    Like the register command, there must be at least one trigger.
    If the mode is set to `set`, then the `trigger` parameter is optional, and it will replace all previous triggers. If there's no triggers, then the proxy cannot be used through regular means.
    If the mode is set to `add`, then the `trigger` parameter is required, and it will be appended to the trigger list.
    If the mode is set to `remove`, then it will try to remove `trigger` from the trigger list, and if none is supplied, it will remove all triggers.
    """, 'set triggers <proxy> <"set" OR "add" OR "remove"> [trigger]',
                      ['set triggers 69ed73 add egg: {}', 'set triggers 69ed73 set hi{}!', 'set triggers 69ed73 remove hi{}!', 'set triggers 69ed73 remove', 'set triggers 69ed73 set'], "proxy_act")
    async def change_triggers(message: fluxer.Message, id_: str, mode: str, trigger: str | None):
        if not await valid_template(message, "Trigger", trigger):
            return

        if mode == "add" and trigger is None:
            await response.respond(message, 'Error! "add" mode must have triggers to add!')
            return

        proxy = await ensure_own_proxy(message, id_)
        if not proxy: return

        new_triggers = proxy.triggers
        if mode == "set":
            new_triggers = [trigger]
        elif mode == "remove":
            if trigger in new_triggers:
                new_triggers.remove(trigger)
        elif mode == "add":
            new_triggers.append(trigger)
            new_triggers = [*set(new_triggers)]

        await Database.instance.update_trigger(proxy.id, new_triggers)
        embed = fluxer.Embed(
            "Proxy Updated!",
            f"The trigger for **{proxy.name}** has been changed to {', '.join('`' + trigger + '`' for trigger in new_triggers)}!\nSay hello with it by typing `{example_trigger_text(triggers[0])}`{' or by other triggers' if len(new_triggers) != 1 else ''}!"
        )
        await response.respond(message, "", [embed])

    @register_command([str, proxy_username], bot, "set name", """
    Updates a proxy's name.
    The `new name` argument will be displayed as the name of your proxy after changing it, only if there is no nickname.
    Names can be used in place of proxy IDs in commands.
    """, "set name <proxy> <new name>", ['set name 69ed73 "Sweet Little Egghead"', 'set name 69ed73 Chloe'],
                      "proxy_act")
    async def change_name(message: fluxer.Message, id_: str, new_name: str):
        proxy = await ensure_own_proxy(message, id_)
        if not proxy: return

        old_name = proxy.name
        new_name = normalize_emojis(new_name)
        await Database.instance.update_name(proxy.id, new_name)
        embed = fluxer.Embed(
            "Proxy Updated!",
            f"The name for the previous *{old_name}* has been changed to **{new_name}**!"
        )
        await response.respond(message, "", [embed])

    @register_command([str, optional_type(proxy_username)], bot, "set nickname", """
    Updates a proxy's nickname.
    The `new nickname` argument will always be displayed as the name of your proxy after changing it.
    If `new nickname` is not provided, the nickname will instead be cleared
    """, "set nickname <proxy> [new nickname]", ['set nickname 69ed73', 'set nickname 69ed73 "Chloe (she/her)"'],
                      "proxy_act")
    async def change_nickname(message: fluxer.Message, id_: str, new_nickname: str | None):
        proxy = await ensure_own_proxy(message, id_)
        if not proxy: return

        old_name = proxy.name
        new_nickname = normalize_emojis(new_nickname)
        await Database.instance.update_nickname(proxy.id, new_nickname)
        embed = fluxer.Embed(
            "Proxy Updated!",
            f"The nickname for *{old_name}* has been " + (
                f"changed to **{new_nickname}**!" if new_nickname else "cleared!")
        )
        await response.respond(message, "", [embed])

    @register_command([str, optional_type(str)], bot, "set description", """
    Updates a proxy's description.
    If `new description` is not provided, the description for the proxy will be cleared.
    """, 'set description <proxy> [new description]',
                      ['set description 69ed73 Caring; sweet; likes puppies.', 'set description 69ed73'],
                      "proxy_act")
    async def change_description(message: fluxer.Message, id_: str, new_description: str | None):
        proxy = await ensure_own_proxy(message, id_)
        if not proxy: return
        if new_description is None:
            new_description = ""

        await Database.instance.update_description(proxy.id, new_description)
        if new_description:
            embed = fluxer.Embed(
                "Proxy Updated!",
                f"The description for {proxy.name} has been changed! New description:\n" +
                "\n".join("> " + line for line in new_description.split("\n"))
            )
        else:
            embed = fluxer.Embed(
                "Proxy Updated!",
                f"The description for {proxy.name} has been cleared!"
            )
        await response.respond(message, "", [embed])

    @register_command([], bot, "nuke", """
    Deletes every proxy associated with your account.
    This action is irreversible! Make sure you really want to do this!
    """, "nuke", ["nuke"], "proxy_act")
    async def nuke(message: fluxer.Message):
        proxies = await Database.instance.get_user_proxies(int(message.author.id))

        if not proxies:
            await response.respond(message, "You have no proxies to delete!")
            return

        m = await response.respond(message,
                                   f"> [!CAUTION]\n> Are you sure you want to nuke **all of your {len(proxies)} proxies**? React to the :white_check_mark: to confirm. This message will expire in 10 seconds.")
        await m.add_reaction("✅")
        msg_id = int(m.id)

        async def cb(event: RawReactionActionEvent):
            if event.emoji.name == "✅":
                await Database.instance.delete_data(int(message.author.id))
                await response.respond(message, f"Successfully nuked your proxies!")

        Interactions.instance.add_interaction(msg_id, Interaction(message.author.id, cb, 10))

        if await Interactions.instance.wait_claim_after(10, msg_id, message.author.id):
            await m.edit("Proxy nuke confirmation expired!")
            await remove_reaction(m, "✅")