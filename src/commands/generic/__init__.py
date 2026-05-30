import inspect
from typing import Callable, Coroutine, Any

from .data import Command, Argument, CharacterStream, ParsingArgument, ParseError
from .strategies import strategize
from ...service import Context, Platform

type CommandCallable[Ctx] = Callable[[Ctx, ...], Coroutine[Any, Any, Any]]

command_registry: dict[str, Command] = {}
command_hooks: dict[tuple[str, Platform], CommandCallable[Context]] = {}


def make_command(
        name: dict[str, list[str]] | str,
        brief: str,
        description: str,
        arguments: list[Argument]
):
    global command_registry

    if isinstance(name, dict):
        n = [*name.keys()][0]
        aliases = name[n]
    else:
        n = name
        aliases = []

    command = Command(n, aliases, brief, description, arguments)
    command_registry[n] = command

    command_registry = dict(sorted(command_registry.items(), key=lambda kv: len(kv[0]), reverse=True))


def hook_command[Ctx = Context](name: str, platform: Platform | None = None) -> Callable[[CommandCallable[Ctx]], None]:
    if name not in command_registry:
        raise KeyError(f"Command {name!r} not found.")

    def wrap(inner: CommandCallable[Ctx]):
        sig = inspect.signature(inner)
        arg_count = len(sig.parameters)
        cmd = command_registry[name]
        if arg_count != len(cmd.arguments) + 1: # +1 for context
            raise KeyError(f"Hook for {name!r} for {platform.name if platform else 'all platforms'} does not have the expected number of parameters.")

        if platform is None:
            for plat in Platform:
                command_hooks[name, plat] = inner
        else:
            command_hooks[name, platform] = inner
    return wrap


async def parse_command_arguments(clean_string: str, arguments: list[Argument], context: Context) -> list[Any]:
    stream = CharacterStream(clean_string)
    results = []
    for idx, arg in enumerate(arguments):
        strat = strategize(arg.strategy)

        if not strat.accept_end_of_stream and stream.end:
            raise ParseError(f"unexpected end of arguments while trying to parse argument #{idx + 1} `{arg.name}`")

        try:
            results.append(await strat.parse(stream, ParsingArgument(arg, idx, len(arguments) - idx - 1), context))
        except ParseError as e:
            raise ParseError(f"error parsing argument #{idx + 1} `{arg.name}`: {e.message}")
        stream.expect_argument_end()
    return results


async def get_command_awaitable(context: Context, prefixes: list[str]) -> Coroutine[Any, Any, Any] | None:
    for prefix in prefixes:
        if context.message_content.startswith(prefix):
            sans_prefix = context.message_content[len(prefix):].strip()
            for name, command in command_registry.items():
                if any(sans_prefix.lower().startswith((matched_name := n).lower()) for n in [command.canonical_name] + command.aliases):
                    arguments = await parse_command_arguments(sans_prefix[len(matched_name):].strip(), command.arguments, context)
                    return command_hooks[name, context.platform](context, *arguments)
    return None
