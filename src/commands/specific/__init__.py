import random
from typing import Awaitable, Any

from textdistance import damerau_levenshtein as edit_distance

from ..generic import CharacterStream, ParsingArgument, EarlyExitException
from ..generic.data import Strategy, SyntaxParseError, ParseError
from ..generic.misc import escape_string
from ..generic.strategies import OneOf, HexadecimalStrategy, StringStrategy, IntegerStrategy
from ...backend.config import Config
from ...backend.database import Database
from ...backend.models import Proxy, ProxyGroup
from ...backend.template_utils import Template, ExprPart
from ...backend.utils import normalize_emojis
from ...service import Context


async def get_uid(context: Context, create: bool = False, on_unregistered: Awaitable[Any] = None) -> int:
    uid = await Database.instance.get_user_id(context.author.id, context.platform, create)
    if uid == -1 and on_unregistered:
        await on_unregistered
        raise EarlyExitException()
    return uid


class ProxyStrategy(Strategy):
    def __init__(self, enforce_ownership: bool = True):
        self.enforce_ownership = enforce_ownership

    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> Proxy:
        owner = await get_uid(context)
        try:
            prox = await OneOf(hex, str).parse(stream, argument, context)
            if isinstance(prox, int):
                proxy = await Database.instance.get_proxy(prox)

                if not proxy:
                    raise ParseError("this proxy does not exist")

                if self.enforce_ownership and proxy.owner != owner:
                    raise ParseError("you do not own this proxy")

            else:
                norm_name = normalize_emojis(prox)
                user_proxies = await Database.instance.get_user_proxies(owner)
                if not user_proxies:
                    raise ParseError("you do not own any proxies")

                distances = {
                    i: min(
                        edit_distance(
                            norm_name.lower(), candidate.name.lower()
                        ),
                        edit_distance(
                            norm_name.lower(), (candidate.nickname or candidate.name).lower()
                        )
                    )
                    for i, candidate in enumerate(user_proxies)
                }
                minimum_distance = min(distances.items(), key=lambda kv: kv[1])
                if minimum_distance[1] > 5 or [*distances.values()].count(minimum_distance[1]) > 1:
                    raise ParseError(f"cannot pinpoint a proxy from its name")

                proxy = user_proxies[minimum_distance[0]]

            return proxy

        except SyntaxParseError:
            raise SyntaxParseError(f"not a valid proxy ID nor a proxy name")


    def example(self) -> str:
        return random.choice(["proxy", "\"proxy name\"", HexadecimalStrategy().example()])

    def get_placeholder_text(self) -> str:
        return "proxy"


class ProxyGroupStrategy(Strategy):
    def __init__(self, enforce_ownership: bool = True):
        self.enforce_ownership = enforce_ownership

    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> ProxyGroup:
        owner = await get_uid(context)
        try:
            grp = await OneOf(hex, str).parse(stream, argument, context)
            if isinstance(grp, int):
                group = await Database.instance.get_group(grp)

                if not group:
                    raise ParseError("this proxy group does not exist")

                if self.enforce_ownership and group.owner != owner:
                    raise ParseError("you do not own this proxy group")

            else:
                norm_name = normalize_emojis(grp)
                user_groups = await Database.instance.get_user_groups(owner)
                if not user_groups:
                    raise ParseError("you do not own any proxy groups")

                distances = {
                    i: edit_distance(
                        norm_name.lower(), candidate.name.lower()
                    )
                    for i, candidate in enumerate(user_groups)
                }
                minimum_distance = min(distances.items(), key=lambda kv: kv[1])
                if minimum_distance[1] > 5 or [*distances.values()].count(minimum_distance[1]) > 1:
                    raise ParseError(f"cannot pinpoint a proxy group from its name")

                group = user_groups[minimum_distance[0]]

            return group

        except SyntaxParseError:
            raise SyntaxParseError(f"not a valid proxy group ID nor a group name")


    def example(self) -> str:
        return random.choice(["group", "\"proxy group name\"", HexadecimalStrategy().example()])

    def get_placeholder_text(self) -> str:
        return "proxy group"


class TemplateStrategy(Strategy):
    def __init__(self, variables: list[str], force_template: bool = True):
        self.variables = variables
        self.force_template = force_template

    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> Template:
        string = await StringStrategy().parse(stream, argument, context)
        if "text" in string and "{}" not in string:
            string = string.replace("text", "{}", 1)
            await context.reply(f"Note: {Config.instance.name} uses `{'{}'}` for placeholders instead of `text`. Your input has been auto-coerced to use `{'{}'}`.")

        template = Template.from_string(string)
        if template.errors:
            await context.reply(f"Warning: template parsing encountered errors:\n{'\n'.join(('- ' + err) for err in template.errors)}")

        if template.get_expr_count() == 0 and self.force_template:
            raise ParseError("template must contain the literal `{}`, or have an expression slot")

        for part in template.parts:
            if isinstance(part, ExprPart):
                if part.content:
                    if not all(var in part.content for var in self.variables):
                        raise ParseError(f"template, if not empty, must refer one of these variables: `{'`, `'.join(self.variables)}`")

        return template


    def example(self) -> str:
        string = random.choice(["prefix, ", ""]) + random.choice(["{}"] + ["{" + var + "}" for var in self.variables])
        for _ in range(random.randint(0, 2)):
            string += ", infix, " + random.choice(["{}"] + ["{" + var + "}" for var in self.variables])

        string += random.choice([", suffix", ""])

        return escape_string(string)

    def get_placeholder_text(self) -> str:
        return "template"


class UnknownPageNumber(IntegerStrategy):
    async def parse(self, stream: CharacterStream, argument: ParsingArgument, context: Context) -> int:
        num = await super().parse(stream, argument, context)
        if num < 1:
            raise ParseError(f"{num} is out of range 1~..")

        return num - 1

    def example(self) -> str:
        return str(random.randint(0, 10))

    def get_placeholder_text(self) -> str:
        return "page"
