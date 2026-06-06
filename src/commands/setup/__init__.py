from . import bot_commands, proxy_commands, proxy_action_commands, group_commands, io_commands, guild_commands, user_commands, dice_commands

modules = [bot_commands, proxy_commands, proxy_action_commands, group_commands, io_commands, guild_commands, user_commands, dice_commands]

def setup():
    for module in modules:
        module.setup()

    bot_commands.setup_help_command()