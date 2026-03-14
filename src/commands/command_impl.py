import fluxer
from . import utils
from .. import response

def setup(bot: fluxer.Bot):
    response.set_consts(bot)
    utils.set_consts(bot)

    from . import bot_commands, proxy_commands, proxy_action_commands, group_commands, io_commands, guild_commands, user_commands, dice_commands
    modules = [
        bot_commands,
        proxy_commands,
        proxy_action_commands,
        group_commands,
        io_commands,
        guild_commands,
        user_commands,
        dice_commands
    ]

    for module in modules:
        module.setup(bot)

