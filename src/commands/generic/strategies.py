import random
from typing import Any

import discord
import fluxer

from .data import Strategy, CharacterStream, ParseError, SyntaxParseError, ParsingArgument, Strategible
from .misc import lorem_ipsum
from ...service import Context


def strategize(strategy: Strategible) -> Strategy:
    if isinstance(strategy, Strategy): return strategy
    elif isinstance(strategy, range): return RangeStrategy(strategy)
    elif strategy == int: return IntegerStrategy()
    elif strategy == float: return FloatStrategy()
    elif strategy == str: return StringStrategy()
    elif strategy == bool: return BooleanStrategy()
    elif strategy == hex: return HexadecimalStrategy()
    elif strategy == fluxer.User: return UserStrategy[fluxer.User]()
    elif strategy == fluxer.Channel: return ChannelStrategy[fluxer.Channel]()
    elif strategy == fluxer.Role: return RoleStrategy[fluxer.Role]()
    elif strategy == discord.User: return UserStrategy[discord.User]()
    elif strategy == discord.Channel: return ChannelStrategy[discord.Channel]()
    elif strategy == discord.Role: return RoleStrategy[discord.Role]()
    raise NotImplementedError # should be unreachable


class RangeStrategy(Strategy):
    def __init__(self, r: range):
        self.range = r

    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> int:
        num = await IntegerStrategy().parse(stream, argument, context)
        if num in self.range:
            return num
        raise ParseError(f"{num} is out of range {self.get_placeholder_text()}")

    def example(self) -> str:
        return f"{random.randrange(self.range.start, self.range.stop, self.range.step):g}"

    def get_placeholder_text(self) -> str:
        return f"{self.range.start}~{self.range.stop - self.range.step}" + (f":{self.range.step}" if self.range.step != 1 else "")


class IntegerStrategy(Strategy):
    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> int:
        num = stream.expect("1234567890-")
        radix = 10
        alphabet = "1234567890"
        if num == "0" and stream.peek() in "xbo":
            radix, alphabet = {
                "x": (16, "1234567890abcdefABCDEF"),
                "b": (2, "01"),
                "o": (8, "01234567")
            }[stream.consume()]
            num = ""

        while stream.peek() in alphabet + "_":
            num += stream.consume()
        num = num.replace("_", "")
        try:
            return int(num, radix)
        except ValueError:
            raise SyntaxParseError("cannot parse integer")

    def example(self) -> str:
        return str(random.randint(-100, 100))

    def get_placeholder_text(self) -> str:
        return "integer"


class HexadecimalStrategy(Strategy):
    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> int:
        stream.expect(*"0x")
        alphabet = "1234567890abcdef"
        num = ""
        while stream.peek() in alphabet + "_":
            num += stream.consume()
        num = num.replace("_", "")
        try:
            return int(num, 16)
        except ValueError:
            raise SyntaxParseError("cannot parse hexadecimal")

    def example(self) -> str:
        return hex(random.randint(0, 65535))

    def get_placeholder_text(self) -> str:
        return "hexadecimal"


class FloatStrategy(Strategy):
    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> float:
        num = stream.expect("1234567890.-")
        while stream.peek() in "1234567890._":
            c = stream.consume()
            if c != "_":
                num += c

        try:
            return float(num)
        except ValueError:
            raise SyntaxParseError("cannot parse float")

    def example(self) -> str:
        return str(random.random() * 200 - 100)

    def get_placeholder_text(self) -> str:
        return "float"


class StringStrategy(Strategy):
    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> str:
        quote: None | str = None
        if stream.peek() in "'\"":
            quote = stream.consume()

        if quote is None and argument.position_end == 0:
            d = stream.data[stream.pos:]
            stream.pos = len(stream.data)
            return d

        s = ""
        while True:
            c = stream.peek()
            if c == "\\":
                stream.consume()
                s += stream.consume()
            elif quote is None and c in (" ", "\0"):
                return s
            elif c == quote:
                stream.consume()
                return s
            elif c == "\0":
                raise SyntaxParseError("unterminated string")
            else:
                s += stream.consume()

    def example(self) -> str:
        return repr(lorem_ipsum("SHORT")())

    def get_placeholder_text(self) -> str:
        return "string"


class WordStrategy(Strategy):
    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> str:
        s = ""
        while True:
            c = stream.peek()
            if c == "\\":
                stream.consume()
                s += stream.consume()
            elif c in (" ", "\0"):
                return s
            else:
                s += stream.consume()

    def example(self) -> str:
        return lorem_ipsum("MINI")()

    def get_placeholder_text(self) -> str:
        return "word"


class BooleanStrategy(Strategy):
    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> bool:
        s = await WordStrategy().parse(stream, argument, context)
        if s.lower() in ("yes", "yea", "yeah", "yep", "yuh", "1", "on", "affirm", "affirmative", "true", "t", "y"):
            return True
        elif s.lower() in ("no", "not", "nuh", "0", "off", "deny", "neg", "negative", "negate", "false", "f", "n"):
            return False
        raise SyntaxParseError(f"cannot convert {s!r} to boolean")

    def example(self) -> str:
        return random.choice(["true", "false"])

    def get_placeholder_text(self) -> str:
        return "boolean"


class OneOf(Strategy):
    def __init__(self, *strats: Strategible):
        self.strats = [strategize(strat) for strat in strats]

    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> Any:
        start = stream.pos
        for strat in self.strats:
            try:
                return await strat.parse(stream, argument, context)
            except SyntaxParseError:
                stream.pos = start
        raise ParseError(f"none of {len(self.strats)} alternatives matched")

    def example(self) -> str:
        return random.choice(self.strats).example()

    def get_placeholder_text(self) -> str:
        return " OR ".join(strat.get_placeholder_text() for strat in self.strats)


class OptionList(Strategy):
    def __init__(self, options: dict[str, list[str]] | list[str]):
        if isinstance(options, dict):
            self.options = {
                k.lower(): [i.lower() for i in v] for k, v in options.items()
            }
        else:
            self.options = {
                k.lower(): [] for k in options
            }

    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> str:
        s = await StringStrategy().parse(stream, argument, context)
        for k, v in self.options.items():
            if s.lower() in [k] + v:
                return k
        raise ParseError(f"none of {len(self.options)} options matched")

    def example(self) -> str:
        return random.choice([*self.options.keys()])

    def get_placeholder_text(self) -> str:
        return " OR ".join([*self.options.keys()])


class Optional(Strategy):
    def __init__(self, strat: Strategible, default: Any):
        self.strat = strategize(strat)
        self.default = default

    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> Any:
        start = stream.pos
        if not stream.end:
            try:
                return await self.strat.parse(stream, argument, context)
            except SyntaxParseError:
                stream.pos = start
                return self.default
        else:
            return self.default

    def example(self) -> str:
        return random.choice([self.strat.example(), ""])

    def get_placeholder_text(self) -> str:
        return "[" + self.strat.get_placeholder_text() + "]"


class List(Strategy):
    def __init__(self, datatype: Strategible):
        self.datatype = strategize(datatype)

    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> list[Any]:
        l = []
        while not stream.end:
            start = stream.pos
            try:
                l.append(await self.datatype.parse(stream, argument, context))
            except SyntaxParseError:
                stream.pos = start
                break
            stream.expect_argument_end()
        return l

    def example(self) -> str:
        return " ".join(self.datatype.example() for _ in range(random.randint(0, 3)))

    def get_placeholder_text(self) -> str:
        return self.datatype.get_placeholder_text() + "(s)"


class _UseSnowflakeStrategy(Strategy):
    prefix: str

    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> int:
        stream.expect("<")
        stream.expect(*self.prefix)
        id_ = await IntegerStrategy().parse(stream, argument, context)
        stream.expect(">")
        return id_

    def example(self) -> str:
        return f"<{self.prefix}...>"

    def get_placeholder_text(self) -> str:
        return "snowflake"


class UserStrategy[User](_UseSnowflakeStrategy):
    prefix = "@"

    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> User:
        try:
            id_ = await super().parse(stream, argument, context)
            user = await context.get_user(id_)
            if user is not None:
                return user

            raise ParseError(f"cannot locate user ID {id_}")

        except SyntaxParseError:
            raise SyntaxParseError("could not parse user mention")

    def example(self) -> str:
        return "@user"

    def get_placeholder_text(self) -> str:
        return "@user"


class ChannelStrategy[Channel](_UseSnowflakeStrategy):
    prefix = "#"

    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> CharacterStream:
        try:
            id_ = await super().parse(stream, argument, context)
            channel = await context.get_channel(id_)
            if channel is not None:
                return channel

            raise ParseError(f"cannot locate channel ID {id_}")

        except SyntaxParseError:
            raise SyntaxParseError("could not parse channel mention")

    def example(self) -> str:
        return "#channel"

    def get_placeholder_text(self) -> str:
        return "#channel"


class RoleStrategy[Role](_UseSnowflakeStrategy):
    prefix = "@&"

    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> Role:
        try:
            id_ = await super().parse(stream, argument, context)
            role = await context.get_role(id_)
            if role is not None:
                return role

            raise ParseError(f"cannot locate role ID {id_}")

        except SyntaxParseError:
            raise SyntaxParseError("could not parse role mention")

    def example(self) -> str:
        return "@role"

    def get_placeholder_text(self) -> str:
        return "@role"