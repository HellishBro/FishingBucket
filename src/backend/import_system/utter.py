import json
import time

from pydantic import BaseModel, AnyHttpUrl

from .common import Importer
from ..models import ProxyGroup, Proxy


class ProxyTag(BaseModel):
    prefix: str | None = None
    suffix: str | None = None


class UtterMember(BaseModel):
    id: str
    name: str
    displayname: str | None = None
    avatar_url: AnyHttpUrl | None = None
    proxy_tags: list[ProxyTag]
    keep_proxy: bool | None = None
    description: str | None = None
    pronouns: str | None = None


class UtterConfig(BaseModel):
    name_format: str | None = None


class UtterSystem(BaseModel):
    id: str
    name: str | None = None
    tag: str | None = None
    members: list[UtterMember]
    config: UtterConfig | None = None


class UtterImporter(Importer):
    def import_data(self, data: bytes, owner: int):
        root = UtterSystem(**json.loads(data.decode("utf-8")))
        default_group = ProxyGroup(
            None,
            root.name or "New System",
            root.description or "This group is used to house the imported proxies from Utter!",
            owner,
            time.time(),
            (
                ((root.config or UtterConfig()).name_format or "{name} {tag}")
                .replace("{name}", "{}")
                .replace("{tag}", root.tag)
                .replace("{rawname}", "{proxy.name}")
                .replace("{description}", "{proxy.description}")
                .replace("{pronouns}", "{proxy.pronouns}")
            ).strip() or "",
            None
        )

        members_map: dict[str, Proxy] = {}

        for member in root.members:
            triggers = []
            for tag in member.proxy_tags:
                prefix = self.sanitize_potential_template_fragment(tag.prefix or "")
                postfix = self.sanitize_potential_template_fragment(tag.suffix or "")
                if member.keep_proxy:
                    triggers.append(prefix + "{" + f"{prefix!r} + text + {postfix!r}" + "}" + postfix)
                else:
                    triggers.append(prefix + "{}" + postfix)

            p = Proxy(
                None,
                member.name,
                member.description or "",
                str(member.avatar_url) if member.avatar_url else Proxy.random_avatar(),
                triggers,
                owner,
                0,
                time.time(),
                default_group,
                member.displayname or "",
                {},
                None,
                member.pronouns
            )

            members_map[member.id] = p
            self.proxies.append(p)
