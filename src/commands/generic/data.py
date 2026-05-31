from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Any, Literal

import discord
import fluxer

from ...service import Context


class CharacterStream:
    def __init__(self, data: str):
        self.data = data
        self.pos = 0

    @property
    def end(self) -> bool: return self.pos >= len(self.data)

    def peek(self) -> str: return "\0" if self.end else self.data[self.pos]

    def consume(self) -> str:
        curr = self.peek()
        self.pos += 1
        return curr

    def previous(self) -> str: return "\0" if self.pos == 0 else self.data[self.pos - 1]

    def expect_argument_end(self):
        if self.peek() not in ("\0", " "):
            raise SyntaxParseError(f"unexpected another argument; found fragments of the previous argument")

        while self.peek() == " ":
            self.consume()

    def expect(self, *char_alternatives: str) -> str:
        c = ""
        for chars in char_alternatives:
            if self.peek() not in chars:
                raise SyntaxParseError(f"unexpected characters {self.peek()!r}")
            c += self.consume()
        return c


@dataclass
class ParsingArgument:
    argument: Argument
    position: int
    position_end: int


class Strategy(ABC):
    accept_end_of_stream = False
    bracket_start = "<"
    bracket_end = ">"

    @abstractmethod
    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> Any: pass

    @abstractmethod
    def example(self) -> str: pass

    @abstractmethod
    def get_placeholder_text(self) -> str: pass


type Strategible = (
    Strategy |
    type[int] | type[float] | type[str] | type[bool] |
    range |
    Literal[hex] |
    fluxer.User | fluxer.Channel | fluxer.Role |
    discord.User | discord.TextChannel | discord.Role
)


@dataclass
class Argument:
    name: str
    strategy: Strategible
    example: Callable[[], str] | None = None

    def get_example(self) -> str:
        return self.example() if self.example else self.strategy.example()


@dataclass
class Command:
    canonical_name: str
    aliases: list[str]
    brief: str
    description: str
    arguments: list[Argument]

    def get_example_invocation(self) -> str:
        parts = [self.canonical_name]

        for argument in self.arguments:
            parts.append(argument.get_example())

        return " ".join(parts).replace("  ", " ").strip()


    def get_usage(self, strategize: Callable[[Strategible], Strategy]) -> str:
        parts = [self.canonical_name]

        for argument in self.arguments:
            strat = strategize(argument.strategy)
            placeholder = strat.get_placeholder_text().replace("  ", " ")
            part = f"{strat.bracket_start}{argument.name}: {placeholder}{strat.bracket_end}"
            parts.append(part)

        return " ".join(parts).strip()



class ParseError(Exception):
    def __init__(self, message: str = "error while parsing"):
        super().__init__(message)
        self.message = message

class SyntaxParseError(ParseError): pass


@dataclass
class CommandGroup:
    canonical_name: str
    brief: str
    description: str
    commands: list[str]

    def append(self, command: str):
        self.commands.append(command)