import json
import time
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, AnyHttpUrl, PositiveInt, NonNegativeInt

from .common import Importer
from ..models import ProxyGroup, Proxy


class TupperboxTupper(BaseModel):
    id: PositiveInt
    name: str
    brackets: list[str]
    avatar_url: AnyHttpUrl | Literal[""] = None
    posts: NonNegativeInt | None = 0
    show_brackets: bool | None = False
    birthday: datetime | None = None
    description: str | None = None
    tag: str | None = None
    nick: str | None = None
    created_at: datetime | None = None
    group_id: PositiveInt | None = None


class TupperboxGroup(BaseModel):
    id: PositiveInt
    name: str
    description: str | None = None
    tag: str | None = None


class TupperboxRoot(BaseModel):
    tuppers: list[TupperboxTupper]
    groups: list[TupperboxGroup]


class TupperboxImporter(Importer):
    def import_data(self, data: bytes, owner: int):
        root = TupperboxRoot(**json.loads(data.decode("utf-8")))
        group_mapping: dict[int, ProxyGroup] = {}
        for group in root.groups:
            g = ProxyGroup(
                None,
                group.name,
                group.description or "",
                owner,
                time.time(),
                group.tag or "",
                None
            )
            group_mapping[group.id] = g
            self.groups.append(g)

        for tupper in root.tuppers:
            brackets = []
            for i in range(0, len(tupper.brackets), 2):
                prefix = self.sanitize_potential_template_fragment(tupper.brackets[i])
                postfix = self.sanitize_potential_template_fragment(tupper.brackets[i + 1])
                placeholder = "{}"
                if tupper.show_brackets:
                    placeholder = "{" + f"{prefix!r} + text + {postfix!r}" + "}"

                brackets.append(prefix + placeholder + postfix)

            nick = tupper.nick
            if tupper.tag:
                nick = (nick or tupper.name) + " " + tupper.tag

            p = Proxy(
                None,
                tupper.name,
                tupper.description or "",
                str(tupper.avatar_url) if tupper.avatar_url else Proxy.random_avatar(),
                brackets,
                owner,
                tupper.posts or 0,
                tupper.created_at.timestamp() if tupper.created_at else time.time(),
                group_mapping.get(tupper.group_id),
                nick or "",
                {},
                None,
                None
            )

            self.proxies.append(p)
