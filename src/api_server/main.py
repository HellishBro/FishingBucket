from aiohttp.web import *
import aiohttp

from .model_json_adapter import to_json
from .routing import RouteTable
from .api_app import Application

app = Application()

routes = RouteTable(app, "/api/v1")
get, post = routes.get, routes.post

@get(r"/proxy/{proxy_id}")
async def _(request: Request) -> Response:
    return app.respond_json(to_json(await app.context.database.get_proxy(int(request.match_info["proxy_id"]))))

@get(r"/group/{group_id}")
async def _(request: Request) -> Response:
    return app.respond_json(to_json(await app.context.database.get_group(int(request.match_info["group_id"]))))

@get(r"/redirect")
async def _(request: Request) -> Response:
    code = request.url.query["code"]
    async with aiohttp.ClientSession() as session:
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://localhost:8080/api/v1/redirect",
            "client_id": 1483307071562336131,
            "client_secret": "AP2bybXYStn7lMt7bs7i3Due1jLSVraERxnm1mzJMFM"
        }
        form_data = aiohttp.FormData(payload)
        async with session.post("https://api.fluxer.app/v1/oauth2/token", data=form_data) as resp:
            data = await resp.json()
            access_token = data["access_token"]
            refresh_token = data["refresh_token"]
            expires_in = data["expires_in"]