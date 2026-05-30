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


class ParseError(Exception):
    def __init__(self, message: str = "error while parsing"):
        super().__init__(message)
        self.message = message

class SyntaxParseError(ParseError): pass