import aiohttp
from fastapi import HTTPException
from fastapi.params import Depends
from fastapi.responses import RedirectResponse, Response
from fastapi.requests import Request

from .api_app import Application, require_session
from .api_database import Session, Database
from .batch_edit import handle_batch_edit
from .models import Proxy, ProxyGroup, ModifiedItemResponse, BatchEdit, LoginInformation
from ..backend.database import Platform

app = Application()
router = app.create_router("/api/v1")

@router.get("/proxy/{proxy_id}", response_model=Proxy)
async def _(proxy_id: int, session: Session = Depends(require_session)):
    proxy = await app.context.database.get_proxy(proxy_id)
    if session.user_id == proxy.owner:
        return Proxy.from_source(proxy)
    raise HTTPException(403, "Missing permissions to view proxy, or the proxy does not exist!")

@router.get("/proxies", response_model=list[Proxy])
async def _(session: Session = Depends(require_session)) -> list[Proxy]:
    proxies = await app.context.database.get_user_proxies(session.user_id)
    return [Proxy.from_source(proxy) for proxy in proxies]

@router.get("/groups", response_model=list[ProxyGroup])
async def _(session: Session = Depends(require_session)) -> list[ProxyGroup]:
    groups = await app.context.database.get_user_groups(session.user_id)
    return [ProxyGroup.from_source(group) for group in groups]

@router.get("/group/{group_id}", response_model=ProxyGroup)
async def _(group_id: int, session: Session = Depends(require_session)) -> ProxyGroup:
    group = await app.context.database.get_group(group_id)
    if session.user_id == group.owner:
        return ProxyGroup.from_source(group)
    raise HTTPException(403, "Missing permissions to view group, or the group does not exist!")

@router.post("/edit", response_model=ModifiedItemResponse)
async def _(edits: BatchEdit, session: Session = Depends(require_session)) -> ModifiedItemResponse:
    try:
        return await handle_batch_edit(edits, session.user_id, app.context.database)
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.get("/auth", status_code=307)
async def _(redirect_uri: str) -> RedirectResponse:
    return RedirectResponse(f"https://web.fluxer.app/oauth2/authorize?client_id={app.context.config.api_server.client_id}&scope=identify&redirect_uri={redirect_uri}")

@router.post("/auth/login", response_model=LoginInformation)
async def _(request: Request) -> LoginInformation:
    req = await request.json()
    async with aiohttp.ClientSession() as session:
        payload = {
            "grant_type": "authorization_code",
            "code": req.get("code"),
            "redirect_uri": req.get("redirect_uri"),
            "client_id": app.context.config.api_server.client_id,
            "client_secret": app.context.config.api_server.client_secret
        }
        form_data = aiohttp.FormData(payload)
        async with session.post(f"{app.context.config.api_url}/oauth2/token", data=form_data) as resp:
            data = await resp.json()
            access_token = data["access_token"]
            async with session.get(f"{app.context.config.api_url}/users/@me", headers={"Authorization": "Bearer " + access_token}) as resp_user:
                obj = await resp_user.json()
                user_id = int(obj["id"])
                native_id = await app.context.database.get_user_id(user_id, Platform.Fluxer)
                session_id = await Database.instance.new_session(native_id, obj)
                return LoginInformation(session_id=session_id, user=obj)


@router.post("/auth/logout", status_code=204)
async def _(session: Session = Depends(require_session)) -> Response:
    await Database.instance.remove_all_sessions(session.user_id)
    return Response(status_code=204)
