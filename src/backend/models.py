import random
from dataclasses import dataclass
import json
from enum import Enum, auto


class ID(int):
    def __str__(self):
        return hex(self)


@dataclass
class ProxyGroup:
    id: ID | None
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
        return cls(ID(data[0]), data[1], data[2], data[3], data[4], data[5], parent)

@dataclass
class Proxy:
    id: ID | None
    name: str
    description: str
    avatar_url: str
    triggers: list[str]
    owner: int
    times_used: int
    creation_date: float
    group: ProxyGroup | None
    nickname: str | None
    forms: dict[str, str]
    current_form: str | None

    @staticmethod
    def random_avatar() -> str:
        return f"https://raw.githubusercontent.com/fluxerapp/static/refs/heads/main/avatars/{random.randint(0, 5)}.png"

    @classmethod
    def from_database(cls, data: tuple[int, str, str, str, str, int, int, float, int | None, str | None, str | None, str | None], groups: list[ProxyGroup]) -> Proxy:
        group = None
        if data[8] and groups:
            group = [g for g in groups if g.id == data[8]][0]

        return cls(ID(data[0]), data[1], data[2], data[3], data[4].split("\n"), data[5], data[6], data[7], group, data[9], json.loads(data[10] or "{}"), data[11])

    @property
    def effective_name(self) -> str:
        from .template_utils import Template # i've sinned
        n = self.nickname or self.name
        this_group = self.group
        while this_group:
            g = {
                "id": this_group.id,
                "name": this_group.name,
                "description": this_group.description,
                "owner": this_group.owner,
                "creation_date": this_group.creation_date,
                "tag": this_group.tag
            }
            n = Template.from_string(this_group.tag or "{}").compute({
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

    @property
    def effective_avatar(self) -> str:
        return self.forms.get(self.current_form, self.avatar_url)


class Platform(Enum):
    Fluxer = auto()
    Discord = auto()

    def get(self) -> int:
        if self == Platform.Fluxer:
            return 0
        else:
            return 1

    @classmethod
    def from_(cls, id_: int) -> Platform:
        return [Platform.Fluxer, Platform.Discord][id_]