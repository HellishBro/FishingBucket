from . import bot_commands, proxy_commands, proxy_action_commands, group_commands

modules = [bot_commands, proxy_commands, proxy_action_commands, group_commands]

def setup_commands():
    for module in modules:
        module.setup()

