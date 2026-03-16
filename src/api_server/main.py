from aiohttp.web import *

from .model_json_adapter import to_json
from .routing import RouteTable
from .api_app import Application

app = Application()

routes = RouteTable(app, "/api/v1")
get, post = routes.get, routes.post

@get(r"/proxy/{proxy_id:\d+}")
async def hello(request: Request) -> Response:
    return app.respond_json(to_json(await app.context.database.get_proxy(int(request.match_info["proxy_id"]))))
