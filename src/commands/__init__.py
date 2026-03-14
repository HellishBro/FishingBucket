import time
import traceback
from typing import Any, Callable, Coroutine
import fluxer

from ..backend.models import Command, optional_type, one_or_more, alternative, command_types, CommandGroup, string_with_length

command_groups: dict[str, CommandGroup] = {}


class PeekableConsumable:
    def __init__(self, data: str):
        self.data = data
        self.position = 0

    def at_end(self) -> bool: return self.position >= len(self.data)

    def peek(self) -> str: return "\0" if self.at_end() else self.data[self.position]

    def consume(self) -> str:
        curr = self.peek()
        self.position += 1
        return curr

    def previous(self) -> str: return self.data[self.position - 1]

    def expect(self, char: str, err: str):
        if self.consume() != char: raise ValueError(err)


async def parse_type(message: fluxer.Message, final: bool, stream: PeekableConsumable, bot: fluxer.Bot,
                     current_type: command_types) -> Any:
    if isinstance(current_type, optional_type):
        pos = stream.position
        try:
            return await parse_type(message, final, stream, bot, current_type.optional_type)
        except ValueError:
            stream.position = pos
            return None

    if stream.peek() == "\0":
        raise ValueError(f"Unexpected end of command!")

    if isinstance(current_type, one_or_more):
        lst = []
        e = None
        while True:
            pos = stream.position
            try:
                lst.append(await parse_type(message, False, stream, bot, current_type.original_type))
                if stream.peek() == " ":
                    stream.consume()
                elif stream.peek() == "\0":
                    break
                else:
                    raise ValueError(f"Cannot parse character {stream.peek()!r}!")
            except ValueError as err:
                stream.position = pos
                e = err
                break
        if len(lst) == 0:
            raise e or ValueError("At least one value must be provided!")
        if stream.previous() == " ":
            stream.position -= 1
        return lst
    if isinstance(current_type, alternative):
        pos = stream.position
        for alt in current_type.alternatives:
            try:
                return await parse_type(message, final, stream, bot, alt)
            except ValueError:
                stream.position = pos

        raise ValueError("Argument does not match any of the alternatives!")
    if isinstance(current_type, string_with_length):
        res = await parse_type(message, final, stream, bot, str)
        if len(res) >= current_type.length:
            raise ValueError(f"String is too long! Expected at most {current_type.length} characters, got {len(res)}.")
        return res

    if isinstance(current_type, (float, int, str, bool)):
        res = await parse_type(message, final, stream, bot, type(current_type))
        if (isinstance(current_type, str) and res.lower() == current_type.lower()) or res == current_type:
            return res
        raise ValueError(f"Argument does not match literal!")

    if current_type == float:
        n = ""
        while stream.peek() in "1234567890.":
            if "." in n and stream.peek() == ".":
                raise ValueError(f"Invalid number!")
            n += stream.consume()
        return float(n)
    if current_type == int:
        n = ""
        while stream.peek() in "1234567890":
            n += stream.consume()
        return int(n)
    if current_type == str:
        t = ""
        quote_characters = "'\""
        if stream.peek() in quote_characters:
            stop = stream.consume()
        elif final:
            stop = "\0"
        else:
            stop = " "
        while stream.peek() != stop:
            if stream.peek() == "\0":
                if stop == " ": return t
                raise ValueError(f"Unclosed string!")
            t += stream.consume()

        if stop != " ":
            stream.consume()
        return t
    if current_type == bool:
        l: str = (await parse_type(message, False, stream, bot, str)).lower()
        if l in ("yes", "yea", "yeah", "yep", "yuh", "1", "on", "affirm", "affirmative", "true", "t", "y"):
            return True
        elif l in ("no", "not", "nuh", "0", "off", "deny", "neg", "negative", "negate", "false", "f", "n"):
            return False
        raise ValueError("Cannot interpret boolean input!")

    if current_type == fluxer.Channel:
        err = "Invalid channel input!"
        stream.expect("<", err)
        stream.expect("#", err)
        snowflake = await parse_type(message, final, stream, bot, int)
        stream.expect(">", err)
        try:
            channel = await bot.fetch_channel(snowflake)
            guild_id = (await bot.fetch_channel(str(message.channel_id))).guild_id
            if channel.guild_id != guild_id:
                raise ValueError("Channel is not in the current community!")
        except:
            raise ValueError(f"Inaccessible channel!")

        return channel
    if current_type == fluxer.User:
        err = "Invalid user input!"
        stream.expect("<", err)
        stream.expect("@", err)
        snowflake = await parse_type(message, final, stream, bot, int)
        stream.expect(">", err)
        try:
            user = await bot.fetch_user(snowflake)
        except:
            raise ValueError(f"Unknown user!")

        return user

    raise ValueError(
        f"Unrecognized type: {current_type.__name__ if hasattr(current_type, '__name__') else current_type.__class__.__name__}.")


async def parse_command(message: fluxer.Message, shape: list[command_types], bot: fluxer.Bot, command_name: str) -> list[Any]:
    stripped = message.content[len(bot.command_prefix):].strip()[len(command_name):].strip()
    stream = PeekableConsumable(stripped)
    converted = []
    for i, current_type in enumerate(shape):
        if stream.peek() == "\0" and not isinstance(current_type, optional_type):
            raise ValueError(f"Too few arguments! Expected {len(shape)} arguments, instead got {len(converted)}!")
        try:
            pv = await parse_type(message, i + 1 == len(shape), stream, bot, current_type)
            converted.append(pv)
        except ValueError as e:
            raise ValueError(f"Argument {i + 1}: {e.args[0]}")
        if stream.peek() in " \0":
            stream.consume()
            while stream.peek() in " ":
                stream.consume()
        elif pv is not None:
            raise ValueError(
                f"Argument {i + 1}: Extraneous characters in argument! Found character {stream.peek()!r} in position {stream.position}")
    return converted


def register_group(id_: str, name: str, description: str):
    command_groups[id_] = CommandGroup(name, description, {})


class CommandList:
    def __init__(self):
        self.registry: dict[str, Callable[[fluxer.Message], Coroutine[None, None, None]]] = {}

    def register(self, command_name: str, handler: Callable[[fluxer.Message], Coroutine[None, None, None]]):
        self.registry[command_name] = handler
        self.registry = dict(sorted(self.registry.items(), key=lambda kv: len(kv[0]), reverse=True))

    def clear(self):
        self.registry.clear()


command_list = CommandList()
users_cd_list = {}
session_command_usages = 0


def pop_cooldown(user: int):
    if user in users_cd_list:
        users_cd_list.pop(user)


def clear():
    command_groups.clear()
    command_list.clear()


def register_command(shape: list[command_types], bot: fluxer.Bot, command_name: str, command_description: str,
                     command_usage: str, examples: list[str], group_id: str):
    command_description = "\n".join(line.strip() for line in command_description.strip().split("\n"))

    def decorator(f: Callable[[fluxer.Message, ...], Coroutine[None, None, None]]):
        c = Command(shape, command_name, command_description, command_usage, examples)
        command_groups[group_id].register(c)

        async def wrapper(m: fluxer.Message):
            global session_command_usages
            for u, t in [*users_cd_list.items()]:
                if t <= time.time() - 120:
                    users_cd_list.pop(u)

            author = m.author.id
            if author in users_cd_list:
                await m.reply("Please wait for the previous command to finish!")
                return

            try:
                parsed = await parse_command(m, shape, bot, command_name)
            except ValueError as e:
                await m.reply(
                    f"Error parsing command! {e.args[0]}\nUse `{bot.command_prefix}help {command_name}` for further information.")
                return

            users_cd_list[author] = time.time()
            try:
                session_command_usages += 1
                await f(m, *parsed)
            except Exception as e:
                print("".join(traceback.format_exception(type(e), e, e.__traceback__)))
            finally:
                if author in users_cd_list:
                    users_cd_list.pop(author)

        command_list.register(command_name, wrapper)
        return wrapper

    return decorator

