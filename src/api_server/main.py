import aiohttp
from fastapi import HTTPException
from fastapi.params import Depends
from fastapi.responses import RedirectResponse, Response
from fastapi.requests import Request

from .api_app import Application, require_session
from .api_database import Session, Database, this_time, SESSION_TTL
from .batch_edit import handle_batch_edit
from .models import Proxy, ProxyGroup, ModifiedItemResponse, BatchEdit, LoginInformation, RefreshLogin
from ..backend.models import Platform

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
    if session.user_id == -1:
        return []
    proxies = await app.context.database.get_user_proxies(session.user_id)
    return [Proxy.from_source(proxy) for proxy in proxies]

@router.get("/groups", response_model=list[ProxyGroup])
async def _(session: Session = Depends(require_session)) -> list[ProxyGroup]:
    if session.user_id == -1:
        return []
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
        if session.user_id == -1:
            uid = await app.context.database.get_user_id(session.sso_id, session.platform, True)
            session = await Database.instance.update_user_id(session.session_id, uid)

        return await handle_batch_edit(edits, session.user_id, app.context.database)
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.get("/auth/discord", status_code=307)
async def _(redirect_uri: str) -> RedirectResponse:
    return RedirectResponse(f"https://discord.com/oauth2/authorize?client_id={app.context.config.api_server.discord.client_id}&response_type=code&redirect_uri={redirect_uri}&scope=identify")

@router.get("/auth/fluxer", status_code=307)
async def _(redirect_uri: str) -> RedirectResponse:
    return RedirectResponse(f"https://web.fluxer.app/oauth2/authorize?client_id={app.context.config.api_server.fluxer.client_id}&scope=identify&redirect_uri={redirect_uri}")

@router.post("/auth/fluxer/login", response_model=LoginInformation)
async def _(request: Request) -> LoginInformation:
    req = await request.json()
    async with aiohttp.ClientSession() as session:
        payload = {
            "grant_type": "authorization_code",
            "code": req.get("code"),
            "redirect_uri": req.get("redirect_uri"),
            "client_id": app.context.config.api_server.fluxer.client_id,
            "client_secret": app.context.config.api_server.fluxer.client_secret
        }
        form_data = aiohttp.FormData(payload)
        async with session.post(f"{app.context.config.fluxer.api_url}/oauth2/token", data=form_data) as resp:
            data = await resp.json()
            access_token = data["access_token"]
            async with session.get(f"{app.context.config.fluxer.api_url}/users/@me", headers={"Authorization": "Bearer " + access_token}) as resp_user:
                obj = await resp_user.json()
                user_id = int(obj["id"])
                native_id = await app.context.database.get_user_id(user_id, Platform.Fluxer, False)
                session_id, expires = await Database.instance.new_session(native_id, obj, Platform.Fluxer, user_id)
                return LoginInformation(session_id=session_id, user=obj, platform="fluxer", expires=expires)

@router.post("/auth/discord/login", response_model=LoginInformation)
async def _(request: Request) -> LoginInformation:
    req = await request.json()
    async with aiohttp.ClientSession() as session:
        payload = {
            "grant_type": "authorization_code",
            "code": req.get("code"),
            "redirect_uri": req.get("redirect_uri"),
            "client_id": app.context.config.api_server.discord.client_id,
            "client_secret": app.context.config.api_server.discord.client_secret
        }
        async with session.post(
                f"{app.context.config.discord.api_url}/oauth2/token",
                data=payload,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
        ) as resp:
            data = await resp.json()
            access_token = data["access_token"]
            async with session.get(f"{app.context.config.discord.api_url}/users/@me", headers={"Authorization": "Bearer " + access_token}) as resp_user:
                obj = await resp_user.json()
                user_id = int(obj["id"])
                native_id = await app.context.database.get_user_id(user_id, Platform.Discord, False)
                session_id, expires = await Database.instance.new_session(native_id, obj, Platform.Discord, user_id)
                return LoginInformation(session_id=session_id, user=obj, platform="discord", expires=expires)

@router.post("/auth/logout", status_code=204)
async def _(session: Session = Depends(require_session)) -> Response:
    if session.user_id == -1:
        await Database.instance.remove_sessions_sso_id(session.sso_id)
    else:
        await Database.instance.remove_all_sessions(session.user_id)
    return Response(status_code=204)

@router.post("/auth/extend", response_model=RefreshLogin)
async def _(session: Session = Depends(require_session)) -> RefreshLogin:
    now = this_time()
    new_session = await Database.instance.extend_session(session.session_id, now + SESSION_TTL)
    return RefreshLogin(expires=new_session.expires)
