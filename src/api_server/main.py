import aiohttp
from fastapi import HTTPException
from fastapi.params import Depends
from fastapi.responses import RedirectResponse

from .api_app import Application, require_session
from .api_database import Session, Database
from .model_json_adapter import to_json

app = Application()
router = app.create_router("/api/v1")

@router.get("/proxy/{proxy_id}")
async def _(proxy_id: int, session: Session = Depends(require_session)):
    proxy = await app.context.database.get_proxy(proxy_id)
    if session.user_id == proxy.owner:
        return to_json(proxy)
    raise HTTPException(403, "Missing permissions to view proxy, or the proxy does not exist!")

@router.get("/group/{group_id}")
async def _(group_id: int, session: Session = Depends(require_session)):
    group = await app.context.database.get_group(group_id)
    if session.user_id == group.owner:
        return to_json(group)
    raise HTTPException(403, "Missing permissions to view group, or the group does not exist!")

@router.get("/auth")
async def _():
    return RedirectResponse(f"https://web.fluxer.app/oauth2/authorize?client_id={app.context.config.api_server.client_id}&scope=identify&redirect_uri={app.context.config.api_server.url}/api/v1/redirect")

@router.get("/redirect")
async def _(code: str):
    async with aiohttp.ClientSession() as session:
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": f"{app.context.config.api_server.url}/api/v1/redirect",
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
                session_id = await Database.instance.new_session(user_id, obj)
                return {
                    "session_id": session_id
                }
