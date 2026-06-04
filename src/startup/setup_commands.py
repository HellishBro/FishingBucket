from ..commands.setup import bot_commands, proxy_commands, proxy_action_commands

modules = [bot_commands, proxy_commands, proxy_action_commands]

def setup():
    for module in modules:
        module.setup()

    bot_commands.setup_help_command()