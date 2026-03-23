from datetime import datetime
from typing import Literal

import fluxer
import expr_dice_roller as dice
from expr_dice_roller.parser import Parser, Function
from expr_dice_roller.lexer import Lexer
from expr_dice_roller.evaluator import EvalFunc

from .utils import require_permission
from .. import response
from ..backend.database import Database
from ..backend.dice_environments import global_functions
from ..backend.models import alternative, optional_type
from . import register_command, register_group
from ..backend.utils import roll_dice

start_time = datetime.now()

def setup(bot: fluxer.Bot):
    register_group("dice", "Dice Commands", "Commands related to the dice functionality of the bot.")

    @register_command([str], bot, "dice", """
    Rolls dice.
    """, "dice <roll>", ["dice d6", "dice 2d20d1"], "dice", ["d"])
    async def dice_roll(message: fluxer.Message, roll: str):
        guild_id = (await bot.fetch_channel(str(message.channel_id))).guild_id
        user_fns = (await Database.instance.get_user_preferences(message.author.id)).dice_functions
        guild_fns = (await Database.instance.get_guild_preferences(guild_id)).dice_functions
        evaluator = dice.Evaluator()
        if user_fns:
            user_env = dice.Environment.deserialize(evaluator, user_fns)
        else:
            user_env = dice.Environment()
        if guild_fns:
            guild_env = dice.Environment.deserialize(evaluator, guild_fns)
        else:
            guild_env = dice.Environment()

        env = global_functions()
        env.mutable = user_env
        env.immutable = guild_env
        def get_global_environment(): return env
        def set_global_environment(ge):
            nonlocal env
            env = ge
        ret, embed = roll_dice(roll, get_global_environment, set_global_environment)

        await response.respond(message, f"Result: `{ret}`", [embed])


    @register_command([alternative("user", "community", "global", "all"), optional_type(alternative("variables", "functions", "all"))], bot, "dice environment", """
    Gets all dice environment variables or functions, if specified.
    """, 'dice environment <"user" OR "community" OR "global" OR "all"> ["variables" OR "functions" OR "all"]', ["dice environment user", "dice environment community variables", "dice environment all all"], "dice")
    async def environment(message: fluxer.Message, target: Literal["user"] | Literal["community"] | Literal["global"] | Literal["all"], lists: Literal["variables"] | Literal["functions"] | Literal["all"] | None):
        if lists is None:
            lists = "all"

        guild_id = (await bot.fetch_channel(str(message.channel_id))).guild_id
        fns = None
        user_fns = None
        guild_fns = None
        env = None
        if target == "user" or target == "all":
            fns = (await Database.instance.get_user_preferences(message.author.id)).dice_functions
            user_fns = fns
        if target == "community" or target == "all":
            fns = (await Database.instance.get_guild_preferences(guild_id)).dice_functions
            guild_fns = fns
        if target == "global":
            env = global_functions()
        if target == "all":
            evaluator = dice.Evaluator()
            if user_fns:
                user_env = dice.Environment.deserialize(evaluator, user_fns)
            else:
                user_env = dice.Environment()
            if guild_fns:
                guild_env = dice.Environment.deserialize(evaluator, guild_fns)
            else:
                guild_env = dice.Environment()

            env = global_functions()
            for k, v in guild_env.variables.items():
                if k not in env.variables:
                    env.variables[k] = v
            for k, v in user_env.variables.items():
                if k not in env.variables:
                    env.variables[k] = v

        if not env:
            if fns:
                env = dice.Environment.deserialize(dice.Evaluator(), fns)
            else:
                env = dice.Environment()

        description = ""
        if lists == "variables" or lists == "all":
            description += "**Variables**:\n" + (
                "\n".join(f"- `{n}` = {v:g}" for n, v in env.variables.items() if isinstance(v, (int, float)))
                if any(v for v in env.variables.values() if isinstance(v, (int, float))) else
                "*It's pretty lonely in here...*"
            )
        if lists == "functions" or lists == "all":
            if description: description += "\n\n"
            description += "**Functions**:\n" + (
                "\n".join(f"- {v}" for n, v in env.variables.items() if isinstance(v, EvalFunc))
                if any(v for v in env.variables.values() if isinstance(v, EvalFunc)) else
                "*It's pretty lonely in here...*"
            )

        await response.respond(message, "", [fluxer.Embed("Dice Environment", description)])


    @register_command([alternative("user", "community"), str, float], bot, "dice set variable", """
    Sets a variable used in dice expressions.
    """, 'dice set variable <"user" OR "community"> <name> <value>', ["dice set variable user level 10"], "dice")
    async def set_variable(message: fluxer.Message, target: Literal["user"] | Literal["community"], name: str, value: float):
        guild_id = None
        if target == "user":
            fns = (await Database.instance.get_user_preferences(message.author.id)).dice_functions
            preface = "Your"
        else:
            if not await require_permission(message, 0x20, "Manage Community"): return
            guild_id = (await bot.fetch_channel(str(message.channel_id))).guild_id
            fns = (await Database.instance.get_guild_preferences(guild_id)).dice_functions
            preface = "This community's"

        if fns:
            env = dice.Environment.deserialize(dice.Evaluator(), fns)
        else:
            env = dice.Environment()

        env.assign(name, value)

        if target == "user":
            await Database.instance.set_user_preferences(message.author.id, dice_functions=env.serialize())
        else:
            await Database.instance.set_guild_preferences(guild_id, dice_functions=env.serialize())

        await response.respond(message, "", [fluxer.Embed("Dice Variable Set", f"{preface} dice variables has been updated!\n`{name}` = {value:g}")])

    @register_command([alternative("user", "community"), str], bot, "dice set function", """
    Sets a function that can be used in dice expressions.
    """, 'dice set function <"user" OR "community"> <function expression>', ["dice set variable community magic_number() = 42"], "dice")
    async def set_function(message: fluxer.Message, target: Literal["user"] | Literal["community"], expression: str):
        guild_id = None
        if target == "user":
            fns = (await Database.instance.get_user_preferences(message.author.id)).dice_functions
            preface = "Your"
        else:
            if not await require_permission(message, 0x20, "Manage Community"): return
            guild_id = (await bot.fetch_channel(str(message.channel_id))).guild_id
            fns = (await Database.instance.get_guild_preferences(guild_id)).dice_functions
            preface = "This community's"

        tree = Parser(Lexer(expression).lex()).expression()
        if not isinstance(tree, Function):
            await response.respond(message, f"`{expression}` is not a valid function declaration!")
            return

        if fns:
            env = dice.Environment.deserialize(dice.Evaluator(), fns)
        else:
            env = dice.Environment()

        dice.Evaluator(env).visit(tree)

        if target == "user":
            await Database.instance.set_user_preferences(message.author.id, dice_functions=env.serialize())
        else:
            await Database.instance.set_guild_preferences(guild_id, dice_functions=env.serialize())

        await response.respond(message, "", [fluxer.Embed("Dice Function Set", f"{preface} dice functions has been updated!\n{dice.format_expression(expression)}")])

    @register_command([alternative("user", "community"), str], bot, "dice remove variable", """
    Removes a variable that can be used in dice expressions.
    This can remove variables and functions.
    """, 'dice remove variable <"user" OR "community"> <name>', ["dice remove variable user _"], "dice")
    async def remove_variable(message: fluxer.Message, target: Literal["user"] | Literal["community"], name: str):
        guild_id = None
        if target == "user":
            fns = (await Database.instance.get_user_preferences(message.author.id)).dice_functions
            preface = "Your"
        else:
            if not await require_permission(message, 0x20, "Manage Community"): return
            guild_id = (await bot.fetch_channel(str(message.channel_id))).guild_id
            fns = (await Database.instance.get_guild_preferences(guild_id)).dice_functions
            preface = "This community's"

        if fns:
            env = dice.Environment.deserialize(dice.Evaluator(), fns)
        else:
            env = dice.Environment()

        if name in env.variables:
            env.variables.pop(name)

        if target == "user":
            await Database.instance.set_user_preferences(message.author.id, dice_functions=env.serialize())
        else:
            await Database.instance.set_guild_preferences(guild_id, dice_functions=env.serialize())

        await response.respond(message, "", [fluxer.Embed("Dice Variable Removed",
                                                          f"{preface} dice variables has been updated! Variable `{name}` no longer exists.")])