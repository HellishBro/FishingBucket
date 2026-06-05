import json

from pydantic import BaseModel, AnyHttpUrl, PositiveInt, PositiveFloat

from .common import Importer
from ..models import ProxyGroup, Proxy


class NativeGroup(BaseModel):
    name: str
    description: str
    time: PositiveFloat
    tag: str
    parent: str | None


class NativeProxy(BaseModel):
    name: str
    description: str
    avatar_url: AnyHttpUrl
    triggers: list[str]
    times_used: PositiveInt
    time: PositiveFloat
    group: str | None
    nickname: str
    forms: dict[str, AnyHttpUrl]
    current_form: str | None


class NativeRoot(BaseModel):
    proxies: list[NativeProxy]
    groups: dict[str, NativeGroup]


class NativeImporter(Importer):
    def import_data(self, data: bytes, owner: int):
        root = NativeRoot(**json.loads(data.decode("utf-8")))

        parsed_groups: dict[str, ProxyGroup] = {}
        groups_queue: dict[str, NativeGroup] = {}
        for idx, group in root.groups.items():
            g = ProxyGroup(
                None,
                group.name,
                group.description,
                owner,
                group.time,
                group.tag,
                None
            )
            parsed_groups[idx] = g
            groups_queue[idx] = group

        for proxy in root.proxies:
            self.proxies.append(Proxy(
                None,
                proxy.name,
                proxy.description,
                str(proxy.avatar_url),
                proxy.triggers,
                owner,
                proxy.times_used,
                proxy.time,
                parsed_groups.get(proxy.group, None),
                proxy.nickname,
                {
                    k: str(v)
                    for k, v in proxy.forms.items()
                },
                proxy.current_form
            ))

        while groups_queue:
            to_remove: list[str] = []
            for idx, group in groups_queue.items():
                if group.parent not in groups_queue:
                    parsed_groups[idx].parent = parsed_groups.get(group.parent, None)
                    to_remove.append(idx)

            for idx in to_remove:
                groups_queue.pop(idx)

