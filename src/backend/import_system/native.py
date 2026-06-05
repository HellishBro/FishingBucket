import json

from pydantic import BaseModel, AnyHttpUrl, PositiveInt, PositiveFloat

from . import Exporter
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

class NativeExporter(Exporter):
    def export_data(self) -> bytes:
        serialized_groups: dict[str, NativeGroup] = {}
        serialized_proxies: list[NativeProxy] = []

        group_obj_idx_map: dict[int, str] = {}
        for idx, group in enumerate(self.groups):
            serialized_groups[f"${idx}"] = NativeGroup(
                name=group.name,
                description=group.description or "",
                time=group.creation_date,
                tag=group.tag or "",
                parent=None
            )
            group_obj_idx_map[id(group)] = f"${idx}"

        for idx, group in enumerate(self.groups):
            if group.parent:
                serialized_groups[f"${idx}"].parent = group_obj_idx_map[id(group.parent)]

        for proxy in self.proxies:
            serialized_proxies.append(NativeProxy(
                name=proxy.name,
                description=proxy.description or "",
                avatar_url=AnyHttpUrl(proxy.avatar_url),
                triggers=proxy.triggers,
                times_used=proxy.times_used or 0,
                time=proxy.creation_date,
                group=group_obj_idx_map.get(id(proxy.group), None),
                nickname=proxy.nickname or "",
                forms=proxy.forms or {},
                current_form=proxy.current_form or None
            ))

        data = NativeRoot(proxies=serialized_proxies, groups=serialized_groups)
        return data.model_dump_json().encode("utf-8")

    @property
    def filename(self) -> str:
        return "proxies.json"