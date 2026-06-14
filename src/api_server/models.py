from typing import Literal
from pydantic import BaseModel, Field

from ..backend import models as source_models

class EphemeralID(BaseModel):
    index: int

    def __hash__(self) -> int:
        return hash(f"new {self.index}")


class ProxyGroup(BaseModel):
    id: int | EphemeralID
    name: str
    description: str | None
    creation_date: float
    tag: str | None
    parent: int | EphemeralID | None

    @classmethod
    def from_source(cls, source: source_models.ProxyGroup) -> ProxyGroup:
        return cls(id=source.id, name=source.name, description=source.description,
                   creation_date=source.creation_date, tag=source.tag, parent=source.parent.id if source.parent else None)

    def to_source(self, id_slot: int | None, parent_slot: source_models.ProxyGroup | None, owner: int) -> source_models.ProxyGroup:
        return source_models.ProxyGroup(id_slot, self.name, self.description, owner, self.creation_date, self.tag, parent_slot)

class Proxy(BaseModel):
    id: int | EphemeralID
    name: str
    description: str | None
    avatar_url: str
    triggers: list[str]
    times_used: int
    creation_date: float
    group: int | EphemeralID | None
    nickname: str | None
    forms: dict[str, str]
    current_form: str | None
    effective_name: str
    pronouns: str | None

    @classmethod
    def from_source(cls, source: source_models.Proxy) -> Proxy:
        return cls(id=source.id, name=source.name, description=source.description, avatar_url=source.avatar_url,
                   triggers=source.triggers, times_used=source.times_used, creation_date=source.creation_date,
                   group=source.group.id if source.group else None, nickname=source.nickname, forms=source.forms,
                   current_form=source.current_form, effective_name=source.effective_name, pronouns=source.pronouns)

    def to_source(self, id_slot: int | None, group_slot: source_models.ProxyGroup | None, owner: int) -> source_models.Proxy:
        return source_models.Proxy(id_slot, self.name, self.description, self.avatar_url, self.triggers, owner,
                                   self.times_used, self.creation_date, group_slot, self.nickname, self.forms, self.current_form, self.pronouns)


class NewProxyEdit(BaseModel):
    edit_type: Literal["NEW_PROXY"]
    proxy: Proxy

class NewProxyGroupEdit(BaseModel):
    edit_type: Literal["NEW_PROXY_GROUP"]
    group: ProxyGroup

class DeleteProxyEdit(BaseModel):
    edit_type: Literal["DELETE_PROXY"]
    proxy_id: int

class DeleteProxyGroupEdit(BaseModel):
    edit_type: Literal["DELETE_PROXY_GROUP"]
    group_id: int

class EditProxyName(BaseModel):
    field: Literal["name"]
    value: str

class EditProxyDescription(BaseModel):
    field: Literal["description"]
    value: str | None

class EditProxyAvatarURL(BaseModel):
    field: Literal["avatar_url"]
    value: str

class EditProxyTriggers(BaseModel):
    field: Literal["triggers"]
    value: list[str]

class EditProxyGroup(BaseModel):
    field: Literal["group"]
    value: int | EphemeralID | None

class EditProxyNickname(BaseModel):
    field: Literal["nickname"]
    value: str | None

class EditProxyForms(BaseModel):
    field: Literal["forms"]
    value: dict[str, str]

class EditProxyCurrentForm(BaseModel):
    field: Literal["current_form"]
    value: str | None

class EditProxyPronouns(BaseModel):
    field: Literal["pronouns"]
    value: str | None

class EditProxyField(BaseModel):
    edit_type: Literal["EDIT_PROXY_FIELD"]
    id: int | EphemeralID
    kv: (
        EditProxyName |
        EditProxyDescription |
        EditProxyAvatarURL |
        EditProxyTriggers |
        EditProxyGroup |
        EditProxyNickname |
        EditProxyForms |
        EditProxyCurrentForm |
        EditProxyPronouns
    ) = Field(discriminator="field")

class EditProxyGroupName(BaseModel):
    field: Literal["name"]
    value: str

class EditProxyGroupDescription(BaseModel):
    field: Literal["description"]
    value: str | None

class EditProxyGroupTag(BaseModel):
    field: Literal["tag"]
    value: str | None

class EditProxyGroupParent(BaseModel):
    field: Literal["parent"]
    value: int | EphemeralID | None

class EditProxyGroupField(BaseModel):
    edit_type: Literal["EDIT_PROXY_GROUP_FIELD"]
    id: int | EphemeralID
    kv: (
        EditProxyGroupName |
        EditProxyGroupDescription |
        EditProxyGroupTag |
        EditProxyGroupParent
    ) = Field(discriminator="field")

class Edit(BaseModel):
    edit: (
            NewProxyEdit |
            NewProxyGroupEdit |
            EditProxyField |
            EditProxyGroupField |
            DeleteProxyEdit |
            DeleteProxyGroupEdit
    ) = Field(discriminator="edit_type")

class BatchEdit(BaseModel):
    edits: list[Edit]

class ItemUpdateResponse[T](BaseModel):
    method: Literal["UPDATE"]
    id: int
    data: T

class ItemNewResponse[T](BaseModel):
    method: Literal["NEW"]
    id: int
    matching_ephemeral_id: int
    data: T

class ItemDeleteResponse[T](BaseModel):
    method: Literal["DELETE"]
    id: int

class ModifiedItem[T](BaseModel):
    type: Literal["PROXY"] | Literal["PROXY_GROUP"]
    item: ItemUpdateResponse[T] | ItemNewResponse[T] | ItemDeleteResponse[T] = Field(discriminator="method")

class ModifiedItemResponse(BaseModel):
    items: list[ModifiedItem[Proxy | ProxyGroup]]

class LoginInformation(BaseModel):
    session_id: str
    user: dict
    platform: Literal["discord"] | Literal["fluxer"]