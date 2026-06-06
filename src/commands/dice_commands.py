from typing import Literal

import expr_dice_roller as dice

from .generic import hook_command
from .specific import get_uid
from .utils import require_permissions
from ..backend.database import Database
from ..backend import database as db
from ..backend.dice_environments import global_functions
from ..backend.utils import roll_dice
from ..service import Context, Embed


def setup():
    @hook_command("dice")
    async def _(context: Context, expression: str):
        channel = await context.get_channel(context.message.channel_id)
        uid = await get_uid(context, on_unregistered=...)

        guild_id = channel.guild_id
        user_fns = (await Database.instance.get_user_preferences(uid)).dice_functions
        guild = db.Guild(guild_id, context.platform)
        guild_fns = (await Database.instance.get_guild_preferences(guild)).dice_functions
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
        ret, embed = roll_dice(expression, get_global_environment, set_global_environment)

        await context.reply(f"Result: `{ret}`", [embed])


    @hook_command("environment list")
    async def _(context: Context, target: Literal["user"] | Literal["community"] | Literal["global"] | Literal["all"], objects: Literal["variables"] | Literal["functions"] | Literal["all"]):
        channel = await context.get_channel(context.message.channel_id)
        uid = await get_uid(context, on_unregistered=...)

        guild_id = channel.guild_id
        guild = db.Guild(guild_id, context.platform)

        fns = None
        user_fns = None
        guild_fns = None
        env = None
        if target == "user" or target == "all":
            fns = (await Database.instance.get_user_preferences(uid)).dice_functions
            user_fns = fns
        if target == "community" or target == "all":
            fns = (await Database.instance.get_guild_preferences(guild)).dice_functions
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
        if objects == "variables" or objects == "all":
            description += "**Variables**:\n" + (
                "\n".join(f"- `{n}` = {v:g}" for n, v in env.variables.items() if isinstance(v, (int, float)))
                if any(v for v in env.variables.values() if isinstance(v, (int, float))) else
                "*It's pretty lonely in here...*"
            )
        if objects == "functions" or objects == "all":
            if description: description += "\n\n"
            description += "**Functions**:\n" + (
                "\n".join(f"- {v}" for n, v in env.variables.items() if isinstance(v, dice.evaluator.EvalFunc))
                if any(v for v in env.variables.values() if isinstance(v, dice.evaluator.EvalFunc)) else
                "*It's pretty lonely in here...*"
            )

        await context.reply("", [Embed("Dice Environment", description)])


    @hook_command("environment set")
    async def _(context: Context, target: Literal["user"] | Literal["community"], name: str, expression: str):
        if target == "user":
            uid = await get_uid(context, on_unregistered=...)
            fns = (await Database.instance.get_user_preferences(uid)).dice_functions
            preface = "Your"
        else:
            await require_permissions(context, lambda p: p.manage_guild)
            channel = await context.get_channel(context.message.channel_id)
            guild_id = channel.guild_id
            guild = db.Guild(guild_id, context.platform)
            fns = (await Database.instance.get_guild_preferences(guild)).dice_functions
            preface = "This community's"

        try:
            tree = dice.Parser(dice.Lexer(expression).lex()).expression()
        except ValueError as e:
            await context.reply(f"Error: error parsing expression: {e.args[0]}")
            return

        if fns:
            env = dice.Environment.deserialize(dice.Evaluator(), fns)
        else:
            env = dice.Environment()

        repr_, val = dice.Evaluator(env).visit(tree)

        if isinstance(tree, dice.parser.Function):
            embed = Embed("Dice Function Set", f"{preface} dice functions has been updated!\n{dice.format_expression(expression)}")
        else:
            env.assign(name, val)
            embed = Embed("Dice Variable Set", f"{preface} dice variables has been updated!\n`{name}` = {val:g}")

        if target == "user":
            await Database.instance.set_user_preferences(uid, dice_functions=env.serialize())
        else:
            await Database.instance.set_guild_preferences(guild, dice_functions=env.serialize())

        await context.reply("", [embed])


    @hook_command("environment remove")
    async def _(context: Context, target: Literal["user"] | Literal["community"], name: str):
        if target == "user":
            uid = await get_uid(context, on_unregistered=...)
            fns = (await Database.instance.get_user_preferences(uid)).dice_functions
            preface = "Your"
        else:
            await require_permissions(context, lambda p: p.manage_guild)
            channel = await context.get_channel(context.message.channel_id)
            guild_id = channel.guild_id
            guild = db.Guild(guild_id, context.platform)
            fns = (await Database.instance.get_guild_preferences(guild)).dice_functions
            preface = "This community's"

        if fns:
            env = dice.Environment.deserialize(dice.Evaluator(), fns)
        else:
            env = dice.Environment()

        if name in env.variables:
            env.variables.pop(name)

        if target == "user":
            await Database.instance.set_user_preferences(uid, dice_functions=env.serialize())
        else:
            await Database.instance.set_guild_preferences(guild, dice_functions=env.serialize())

        await context.reply("", [Embed(
            "Dice Variable Removed",
            f"{preface} dice variables has been updated! Variable `{name}` no longer exists."
        )])
