from . import bot_commands, proxy_commands

modules = [bot_commands, proxy_commands]

def setup_commands():
    for module in modules:
        module.setup()

