from typing import Literal, Type, Generator

from .models import BatchEdit, ModifiedItemResponse, ModifiedItem, ProxyGroup, Proxy, Edit, DeleteProxyEdit, \
    DeleteProxyGroupEdit, ItemDeleteResponse, NewProxyEdit, NewProxyGroupEdit, EphemeralID, EditProxyGroupField, \
    EditProxyField, ItemNewResponse, ItemUpdateResponse
from ..backend.database import Database
from ..backend import models as source

class ID:
    id: int
    type: Literal["PROXY"] | Literal["PROXY_GROUP"]

    def __init__(self, id_: int, type_: Literal["PROXY"] | Literal["PROXY_GROUP"]):
        self.id = id_
        self.type = type_

    def __hash__(self):
        return hash((self.id, self.type))


def filter_edit_type[T](edits: list[Edit], cls: Type[T]) -> Generator[T, None, None]:
    return (edit.edit for edit in edits if isinstance(edit.edit, cls))

async def handle_batch_edit(batch_edit: BatchEdit, owner: int, database: Database) -> ModifiedItemResponse | None:
    async def ensure_proxy(proxy: int | source.Proxy):
        if isinstance(proxy, int):
            proxy = await database.get_proxy(proxy)
        if proxy.owner != owner:
            raise ValueError("Proxy owner does not match the authenticated user.")

    async def ensure_group(group: int | source.ProxyGroup):
        if isinstance(group, int):
            group = await database.get_group(group)
        if group.owner != owner:
            raise ValueError("Proxy group owner does not match the authenticated user.")

    def ensure_new(proxy_or_group: Proxy | ProxyGroup):
        if isinstance(proxy_or_group.id, int):
            raise ValueError("Ephemeral ID expected.")

    async def ensure_id_exists(id_: int | EphemeralID | None, type_: Literal["PROXY"] | Literal["PROXY_GROUP"]):
        if id_ is None: return
        elif isinstance(id_, int):
            if type_ == "PROXY":
                await ensure_proxy(id_)
            else:
                await ensure_group(id_)
        else:
            if len([e_id for e_id in encountered_ephemeral_ids if e_id.type == type_ and e_id.id == id_.index]) == 0:
                raise ValueError("Unknown ID or ephemeral ID.")

    def get_id(id_: int | EphemeralID | None, type_: Literal["PROXY"] | Literal["PROXY_GROUP"]) -> int | None:
        if isinstance(id_, int): return id_
        if id_ is None: return id_
        return id_map[ID(id_.index, type_)]


    id_map: dict[ID, int] = {}
    encountered_ephemeral_ids: list[ID] = []
    modified: list[ModifiedItem[Proxy | ProxyGroup]] = []
    ignored_ids: list[ID] = []

    for delete_proxy_edit in filter_edit_type(batch_edit.edits, DeleteProxyEdit):
        await ensure_proxy(delete_proxy_edit.proxy_id)

    for delete_proxy_group_edit in filter_edit_type(batch_edit.edits, DeleteProxyGroupEdit):
        await ensure_group(delete_proxy_group_edit.group_id)

    for new_proxy_group_edit in filter_edit_type(batch_edit.edits, NewProxyGroupEdit):
        ensure_new(new_proxy_group_edit.group)
        await ensure_id_exists(new_proxy_group_edit.group.parent, "PROXY_GROUP")
        encountered_ephemeral_ids.append(ID(new_proxy_group_edit.group.id.index, "PROXY_GROUP"))

    for new_proxy_edit in filter_edit_type(batch_edit.edits, NewProxyEdit):
        ensure_new(new_proxy_edit.proxy)
        await ensure_id_exists(new_proxy_edit.proxy.group, "PROXY_GROUP")
        encountered_ephemeral_ids.append(ID(new_proxy_edit.proxy.id.index, "PROXY"))

    for edit_proxy_group_edit in filter_edit_type(batch_edit.edits, EditProxyGroupField):
        await ensure_id_exists(edit_proxy_group_edit.id, "PROXY_GROUP")

    for edit_proxy_edit in filter_edit_type(batch_edit.edits, EditProxyField):
        await ensure_id_exists(edit_proxy_edit.id, "PROXY")


    for delete_proxy_edit in filter_edit_type(batch_edit.edits, DeleteProxyEdit):
        ignored_ids.append(ID(delete_proxy_edit.proxy_id, "PROXY"))
        modified.append(ModifiedItem(
            type="PROXY",
            item=ItemDeleteResponse(
                method="DELETE", id=delete_proxy_edit.proxy_id
            )
        ))
        await database.delete_proxy(delete_proxy_edit.proxy_id)

    for delete_proxy_group_edit in filter_edit_type(batch_edit.edits, DeleteProxyGroupEdit):
        ignored_ids.append(ID(delete_proxy_group_edit.group_id, "PROXY_GROUP"))
        modified.append(ModifiedItem(
            type="PROXY_GROUP",
            item=ItemDeleteResponse(
                method="DELETE", id=delete_proxy_group_edit.group_id
            )
        ))
        await database.delete_group(delete_proxy_group_edit.group_id)

    for new_proxy_group_edit in filter_edit_type(batch_edit.edits, NewProxyGroupEdit):
        parent = get_id(new_proxy_group_edit.group.parent, "PROXY_GROUP")
        if parent is not None:
            parent_obj = await database.get_group(parent)
        else:
            parent_obj = None

        transformed = new_proxy_group_edit.group.to_source(None, parent_obj, owner)
        g = await database.put_group(transformed)
        id_map[ID(new_proxy_group_edit.group.id.index, "PROXY_GROUP")] = g.id
        modified.append(ModifiedItem(
            type="PROXY_GROUP",
            item=ItemNewResponse(
                method="NEW", id=g.id, matching_ephemeral_id=new_proxy_group_edit.group.id.index, data=ProxyGroup.from_source(g)
            )
        ))

    for new_proxy_edit in filter_edit_type(batch_edit.edits, NewProxyEdit):
        parent = get_id(new_proxy_edit.proxy.group, "PROXY_GROUP")
        if parent is not None:
            group_obj = await database.get_group(parent)
        else:
            group_obj = None

        transformed = new_proxy_edit.proxy.to_source(None, group_obj, owner)
        p = await database.put_proxy(transformed)
        id_map[ID(new_proxy_edit.proxy.id.index, "PROXY")] = p.id
        modified.append(ModifiedItem(
            type="PROXY",
            item=ItemNewResponse(
                method="NEW", id=p.id, matching_ephemeral_id=new_proxy_edit.proxy.id.index, data=Proxy.from_source(p)
            )
        ))

    edited_proxy_groups: list[int] = []
    edited_proxies: list[int] = []

    for edit_proxy_group_edit in filter_edit_type(batch_edit.edits, EditProxyGroupField):
        if isinstance(edit_proxy_group_edit.id, int) and ID(edit_proxy_group_edit.id, "PROXY_GROUP") in ignored_ids:
            continue
        group_id = get_id(edit_proxy_group_edit.id, "PROXY_GROUP")
        edited_proxy_groups.append(group_id)
        field = edit_proxy_group_edit.kv.field
        value = edit_proxy_group_edit.kv.value
        if field == "name":
            await database.update_group_name(group_id, value)
        elif field == "description":
            await database.update_group_description(group_id, value)
        elif field == "tag":
            await database.update_group_tag(group_id, value)
        elif field == "parent":
            await database.update_group_parent(group_id, get_id(value, "PROXY_GROUP"))

    for edit_proxy_edit in filter_edit_type(batch_edit.edits, EditProxyField):
        if isinstance(edit_proxy_edit.id, int) and ID(edit_proxy_edit.id, "PROXY") in ignored_ids:
            continue
        proxy_id = get_id(edit_proxy_edit.id, "PROXY")
        edited_proxies.append(proxy_id)
        field = edit_proxy_edit.kv.field
        value = edit_proxy_edit.kv.value
        if field == "name":
            await database.update_name(proxy_id, value)
        elif field == "description":
            await database.update_description(proxy_id, value)
        elif field == "avatar_url":
            await database.update_avatar(proxy_id, value)
        elif field == "triggers":
            await database.update_trigger(proxy_id, value)
        elif field == "group":
            await database.update_group(proxy_id, get_id(value, "PROXY_GROUP"))
        elif field == "nickname":
            await database.update_nickname(proxy_id, value)
        elif field == "forms":
            await database.update_forms(proxy_id, value)
        elif field == "current_form":
            await database.update_current_form(proxy_id, value)

    edited_proxy_groups = [*set(edited_proxy_groups)]
    edited_proxies = [*set(edited_proxies)]

    for edited_proxy_group in edited_proxy_groups:
        g = await database.get_group(edited_proxy_group)
        modified.append(ModifiedItem(
            type="PROXY_GROUP",
            item=ItemUpdateResponse(
                method="UPDATE", id=g.id, data=ProxyGroup.from_source(g)
            )
        ))

    for edited_proxy in edited_proxies:
        p = await database.get_proxy(edited_proxy)
        modified.append(ModifiedItem(
            type="PROXY",
            item=ItemUpdateResponse(
                method="UPDATE", id=p.id, data=Proxy.from_source(p)
            )
        ))

    return ModifiedItemResponse(items=modified)
