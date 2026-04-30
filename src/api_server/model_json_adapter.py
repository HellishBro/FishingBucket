from typing import Any

from ..backend.models import Proxy, ProxyGroup

def to_json(obj: Any) -> dict:
    if isinstance(obj, Proxy):
        return _to_json_proxy(obj)
    elif isinstance(obj, ProxyGroup):
        return _to_json_proxygroup(obj)
    elif obj is None:
        return None
    return {
        "error": f"unknown type: {obj.__class__.__name__}"
    }

def _to_json_proxy(proxy: Proxy) -> dict:
    return {
        "id": proxy.id,
        "name": proxy.name,
        "description": proxy.description,
        "avatar_url": proxy.avatar_url,
        "triggers": proxy.triggers,
        "owner": str(proxy.owner),
        "times_used": proxy.times_used,
        "creation_date": proxy.creation_date,
        "group": proxy.group.id if proxy.group else None,
        "nickname": proxy.nickname,
        "effective_name": proxy.effective_name,
        "forms": proxy.forms,
        "current_form": proxy.current_form
    }

def _to_json_proxygroup(group: ProxyGroup) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "owner": str(group.owner),
        "creation_date": group.creation_date,
        "tag": group.tag,
        "parent": group.parent.id if group.parent else None
    }
