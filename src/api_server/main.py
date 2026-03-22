from aiohttp.web import *
import aiohttp

from .api_database import Database, Session
from .model_json_adapter import to_json
from .routing import RouteTable
from .api_app import Application

app = Application()

routes = RouteTable(app, "/api/v1")
get, post = routes.get, routes.post

@get("/proxy/{proxy_id}")
@app.require_session
async def _(request: Request, session: Session) -> Response:
    proxy = await app.context.database.get_proxy(int(request.match_info["proxy_id"]))
    if not proxy:
        raise HTTPNotFound()
    if session.user_id == proxy.owner:
        return json_response(to_json(proxy))
    raise HTTPForbidden()

@get("/group/{group_id}")
@app.require_session
async def _(request: Request, session: Session) -> Response:
    group = await app.context.database.get_group(int(request.match_info["group_id"]))
    if not group:
        raise HTTPNotFound()
    if session.user_id == group.owner:
        return json_response(to_json(group))
    raise HTTPForbidden()

@get("/auth")
async def _(request: Request) -> Response:
    raise HTTPFound(f"https://web.fluxer.app/oauth2/authorize?client_id={app.context.config.api_server.client_id}&scope=identify&redirect_uri={app.context.config.api_server.url}/api/v1/redirect")

@get("/redirect")
async def _(request: Request) -> Response:
    code = request.url.query["code"]
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
            print(data)
            access_token = data["access_token"]
            async with session.get(f"{app.context.config.api_url}/users/@me", headers={"Authorization": "Bearer " + access_token}) as resp_user:
                obj = await resp_user.json()
                print(obj)
                user_id = int(obj["id"])
                session_id = await Database.instance.new_session(user_id, obj)
                return json_response({
                    "session_id": session_id
                })
