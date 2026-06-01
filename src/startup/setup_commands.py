from ..commands.setup import bot_commands, proxy_commands

modules = [bot_commands, proxy_commands]

def setup():
    for module in modules:
        module.setup()

    bot_commands.setup_help_command()