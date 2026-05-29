import random
from typing import Any

from .data import Strategy, CharacterStream, ParseError, ParsingArgument, Strategible
from .misc import lorem_ipsum


def strategize(strategy: Strategible) -> Strategy:
    if isinstance(strategy, Strategy): return strategy
    elif isinstance(strategy, range): return RangeStrategy(strategy)
    elif strategy == int: return IntegerStrategy()
    elif strategy == float: return FloatStrategy()
    elif strategy == str: return StringStrategy()
    elif strategy == bool: return BooleanStrategy()
    raise NotImplementedError # should be unreachable


class RangeStrategy(Strategy):
    def __init__(self, r: range):
        self.range = r

    def parse(self, stream: CharacterStream, argument: ParsingArgument) -> int:
        num = IntegerStrategy().parse(stream, argument)
        if num in self.range:
            return num
        raise ParseError(f"{num} is out of range {self.get_placeholder_text()}")

    def example(self) -> str:
        return f"{random.randrange(self.range.start, self.range.stop, self.range.step):g}"

    def get_placeholder_text(self) -> str:
        return f"{self.range.start}~{self.range.stop - self.range.step}" + (f":{self.range.step}" if self.range.step != 1 else "")


class IntegerStrategy(Strategy):
    def parse(self, stream: CharacterStream, argument: ParsingArgument) -> int:
        if stream.peek() not in "1234567890-":
            raise ParseError()
        num = stream.consume()
        radix = 10
        alphabet = "1234567890"
        if num == "0" and stream.peek() in "xbo":
            radix, alphabet = {
                "x": (16, "1234567890abcdef"),
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
            raise ParseError("cannot parse integer")

    def example(self) -> str:
        return str(random.randint(-100, 100))

    def get_placeholder_text(self) -> str:
        return "integer"


class FloatStrategy(Strategy):
    def parse(self, stream: CharacterStream, argument: ParsingArgument) -> float:
        if stream.peek() not in "1234567890.-":
            raise ParseError()
        num = stream.consume()
        while stream.peek() in "1234567890._":
            c = stream.consume()
            if c != "_":
                num += c

        try:
            return float(num)
        except ValueError:
            raise ParseError("cannot parse float")

    def example(self) -> str:
        return str(random.random() * 200 - 100)

    def get_placeholder_text(self) -> str:
        return "float"


class StringStrategy(Strategy):
    def parse(self, stream: CharacterStream, argument: ParsingArgument) -> str:
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
                raise ParseError("unterminated string")
            else:
                s += stream.consume()

    def example(self) -> str:
        return lorem_ipsum("SHORT")()

    def get_placeholder_text(self) -> str:
        return "string"


class BooleanStrategy(Strategy):
    def parse(self, stream: CharacterStream, argument: ParsingArgument) -> bool:
        s = StringStrategy().parse(stream, argument)
        if s.lower() in ("yes", "yea", "yeah", "yep", "yuh", "1", "on", "affirm", "affirmative", "true", "t", "y"):
            return True
        elif s.lower() in ("no", "not", "nuh", "0", "off", "deny", "neg", "negative", "negate", "false", "f", "n"):
            return False
        raise ParseError(f"cannot convert {s!r} to boolean")

    def example(self) -> str:
        return random.choice(["true", "false"])

    def get_placeholder_text(self) -> str:
        return "boolean"


class OneOf(Strategy):
    def __init__(self, *strats: Strategible):
        self.strats = [strategize(strat) for strat in strats]

    def parse(self, stream: CharacterStream, argument: ParsingArgument) -> Any:
        start = stream.pos
        for strat in self.strats:
            try:
                return strat.parse(stream, argument)
            except ParseError:
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

    def parse(self, stream: CharacterStream, argument: ParsingArgument) -> str:
        s = StringStrategy().parse(stream, argument)
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

    def parse(self, stream: CharacterStream, argument: ParsingArgument) -> Any:
        if not stream.end:
            try:
                return self.strat.parse(stream, argument)
            except ParseError:
                return self.default
        else:
            return self.default

    def example(self) -> str:
        return random.choice([self.strat.example(), ""])

    def get_placeholder_text(self) -> str:
        return "[" + self.strat.get_placeholder_text() + "]"
