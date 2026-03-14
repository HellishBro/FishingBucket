import fluxer
from fluxer.models import RawReactionActionEvent

from .interaction import Interactions, Interaction, message_reactions

bot: fluxer.Bot = None
def set_consts(bot_: fluxer.Bot):
    global bot
    bot = bot_

async def interact(event: RawReactionActionEvent):
    if event.emoji.name == "❌":
        await delete_message_id_channel(event.message_id, event.channel_id)
        return {"pop": True}
    return None

async def respond(message: fluxer.Message, contents: str, embeds: list[fluxer.Embed] | None = None, user_id_override: int | None = None, **kwargs) -> fluxer.Message:
    msg = await message.reply(contents, embeds=embeds, **kwargs)
    Interactions.instance.add_interaction(msg.id, Interaction(user_id_override or message.author.id, interact))
    return msg

async def delete_message(message: fluxer.Message):
    await message.delete()
    finds = [mu for mu in message_reactions.keys() if mu[0] == message.id]
    for find in finds:
        message_reactions.pop(find)

    Interactions.instance.delete_interaction(message.id)

async def delete_message_id_channel(message_id: int, channel_id: int):
    await bot.delete_message(channel_id, message_id)
    finds = [mu for mu in message_reactions.keys() if mu[0] == message_id]
    for find in finds:
        message_reactions.pop(find)

    Interactions.instance.delete_interaction(message_id)
