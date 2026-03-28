import time

from .backend.models import Proxy, ProxyGroup

def import_tupperbox(json: dict, owner: int) -> tuple[list[ProxyGroup], list[Proxy]]:
    groups = json.get("groups", [])
    tuppers = json.get("tuppers", [])
    group_mapping: dict[int, ProxyGroup] = {}
    for group in groups:
        parsed = ProxyGroup.from_tupper(group, owner)
        group_mapping.update(parsed)

    parsed_tuppers: list[Proxy] = []
    for tupper in tuppers:
        parsed_tuppers.append(Proxy.from_tupper(tupper, owner, group_mapping))

    return [*group_mapping.values()], parsed_tuppers


def import_native(json: dict, owner: int) -> tuple[list[ProxyGroup], list[Proxy]]:
    groups: dict[str, dict] = json["groups"]
    proxies: list[dict] = json["proxies"]

    parsed_groups: dict[str, ProxyGroup] = {}
    for idx, group in groups.items():
        parsed_groups[idx] = ProxyGroup(
            None,
            group["name"],
            group["description"],
            owner,
            group["time"],
            group["tag"],
            None
        )
    for idx, group in groups.items():
        if group["parent"]:
            parsed_groups[idx].parent = parsed_groups[group["parent"]]

    parsed_proxies: list[Proxy] = []
    for proxy in proxies:
        parsed_proxies.append(Proxy(
            None,
            proxy["name"],
            proxy["description"],
            proxy["avatar_url"],
            proxy["triggers"],
            owner,
            proxy["times_used"],
            proxy["time"],
            parsed_groups.get(proxy["group"], None),
            proxy["nickname"],
            proxy["forms"]
        ))

    return [*parsed_groups.values()], parsed_proxies


def export_native(groups: list[ProxyGroup], proxies: list[Proxy]) -> dict:
    serialized_groups: dict[str, dict] = {}
    serialized_proxies: list[dict] = []

    group_obj_idx_map: dict[int, str] = {}
    for idx, group in enumerate(groups):
        serialized_groups[f"${idx}"] = {
            "name": group.name,
            "description": group.description,
            "time": group.creation_date,
            "tag": group.tag,
            "parent": None
        }
        group_obj_idx_map[id(group)] = f"${idx}"

    for idx, group in enumerate(groups):
        if group.parent:
            serialized_groups[f"${idx}"]["parent"] = group_obj_idx_map[id(group.parent)]

    for proxy in proxies:
        serialized_proxies.append({
            "name": proxy.name,
            "description": proxy.description,
            "avatar_url": proxy.avatar_url,
            "triggers": proxy.triggers,
            "times_used": proxy.times_used,
            "time": proxy.creation_date,
            "group": group_obj_idx_map.get(id(proxy.group), None),
            "nickname": proxy.nickname,
            "forms": proxy.forms
        })

    return {"groups": serialized_groups, "proxies": serialized_proxies}


def import_pluralkit(json: dict, owner: int) -> tuple[list[ProxyGroup], list[Proxy]]:
    groups = json.get("groups", [])
    members = json.get("members", [])
    tag: str | None = json.get("tag", None)

    default_group = None
    if tag:
        default_group = ProxyGroup(None, "Pluralkit Import Default Group", "This group was used to provide the system tag to the imported proxies from Pluralkit!", owner, time.time(), "{} " + tag, None)

    member_mapping: dict[str, Proxy] = {}
    for member in members:
        p = Proxy.from_pk(member, owner)
        p.group = default_group
        if p: member_mapping[member["id"]] = p

    parsed_groups: list[ProxyGroup] = []
    if default_group:
        parsed_groups.append(default_group)

    for group in groups:
        g = ProxyGroup.from_pk(group, owner)
        for member in group.get("members", []):
            if member in member_mapping:
                member_mapping[member].group = g
        parsed_groups.append(g)

    return parsed_groups, [*member_mapping.values()]
