import random
import time
from dataclasses import dataclass
from datetime import datetime

from .template_utils import Template


@dataclass
class ProxyGroup:
    id: int | None
    name: str
    description: str
    owner: int
    creation_date: float
    tag: str
    parent: ProxyGroup | None

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, ProxyGroup):
            return self.id == other.id
        return False


    @classmethod
    def from_database(cls, data: tuple[int, str, str, int, float, str, int], parent: ProxyGroup | None) -> ProxyGroup:
        return cls(data[0], data[1], data[2], data[3], data[4], data[5], parent)

    @classmethod
    def from_tupper(cls, group: dict, owner: int) -> dict[int, ProxyGroup]:
        return {
            group["id"]: ProxyGroup(
                None,
                group["name"],
                group["description"] or "",
                owner,
                time.time(),
                ("{} " + group["tag"]) if group.get("tag") else "",
                None
            )
        }

    @classmethod
    def from_pk(cls, group: dict, owner: int, tag: str | None) -> ProxyGroup:
        return ProxyGroup(
            None,
            group["name"],
            group["description"] or "",
            owner,
            datetime.fromisoformat(group["created"]).timestamp() if group["created"] else time.time(),
            ("{} " + tag) if tag else "",
            None
        )


@dataclass
class Proxy:
    id: int | None
    name: str
    description: str
    avatar_url: str
    triggers: list[str]
    owner: int
    times_used: int
    creation_date: float
    group: ProxyGroup | None
    nickname: str | None

    @staticmethod
    def random_avatar() -> str:
        return f"https://raw.githubusercontent.com/fluxerapp/static/refs/heads/main/avatars/{random.randint(0, 5)}.png"

    @classmethod
    def from_database(cls, data: tuple[int, str, str, str, str, int, int, float, int | None, str | None], groups: list[ProxyGroup]) -> Proxy:
        group = None
        if data[8] and groups:
            group = [g for g in groups if g.id == data[8]][0]

        return cls(data[0], data[1], data[2], data[3], data[4].split("\n"), data[5], data[6], data[7], group, data[9])

    @staticmethod
    def process_trigger_part(part: str) -> str:
        return part.replace("{", "\\}").replace("}", "\\}")

    @classmethod
    def from_tupper(cls, tupper: dict, owner: int, groups: dict[int, ProxyGroup]) -> Proxy:
        brackets = []
        for i in range(0, len(tupper["brackets"]), 2):
            brackets.append(cls.process_trigger_part(tupper["brackets"][i]) + "{}" + cls.process_trigger_part(tupper["brackets"][i + 1]))

        nick = tupper.get("nick")
        if tag := tupper.get("tag"):
            if nick:
                nick += " " + tag
            else:
                nick = tupper["name"] + " " + tag

        return cls(
            None,
            tupper["name"],
            tupper["description"] or "",
            tupper["avatar_url"] or Proxy.random_avatar(),
            brackets,
            owner,
            tupper["posts"] or 0,
            datetime.fromisoformat(tupper["created_at"]).timestamp() if tupper["created_at"] else time.time(),
            groups.get(tupper["group_id"]),
            nick
        )

    @classmethod
    def from_pk(cls, pluralkit: dict, owner: int) -> Proxy | None:
        return cls(
            None,
            pluralkit["name"],
            pluralkit["description"] or "",
            pluralkit["avatar_url"] or Proxy.random_avatar(),
            [cls.process_trigger_part(i["prefix"] or "") + "{}" + cls.process_trigger_part(i["suffix"] or "") for i in pluralkit["proxy_tags"]] or [],
            owner,
            pluralkit["message_count"],
            datetime.fromisoformat(pluralkit["created"]).timestamp() if pluralkit["created"] else time.time(),
            None,
            pluralkit["display_name"]
        )

    @property
    def effective_name(self) -> str:
        n = self.nickname or self.name
        this_group = self.group
        while this_group and this_group.tag:
            g = {
                "id": this_group.id,
                "name": this_group.name,
                "description": this_group.description,
                "owner": this_group.owner,
                "creation_date": this_group.creation_date,
                "tag": this_group.tag
            }
            n = Template.from_string(this_group.tag).compute({
                "name": n,
                "proxy": {
                    "id": self.id,
                    "name": self.name,
                    "description": self.description,
                    "avatar_url": self.avatar_url,
                    "triggers": self.triggers,
                    "times_used": self.times_used,
                    "creation_date": self.creation_date,
                    "group": g,
                    "nickname": self.nickname
                },
                "group": g
            }, n)
            this_group = this_group.parent
        return n


class optional_type:
    def __init__(self, ot: command_types):
        self.optional_type = ot

class one_or_more:
    def __init__(self, ot: command_types):
        self.original_type = ot

class alternative:
    def __init__(self, *alternatives: command_types):
        self.alternatives = alternatives

class string_with_length:
    def __init__(self, length: int):
        self.length = length

type command_types = type | object | optional_type | optional_type | alternative | string_with_length


@dataclass
class Command:
    shape: list[command_types]
    name: str
    description: str
    usage: str
    examples: list[str]

@dataclass
class CommandGroup:
    name: str
    description: str
    commands: dict[str, Command]

    def register(self, command: Command):
        self.commands[command.name] = command
