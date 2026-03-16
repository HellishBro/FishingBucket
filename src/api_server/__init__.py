from aiohttp.web import *
from routing import RouteTable
import json

routes = RouteTable("/api/v1")

get, post = routes.get, routes.post

@get("/posts/{title}")
async def hello(request: Request) -> Response:
    return Response(body=json.dumps({
        "title": request.match_info["title"]
    }), content_type="application/json")

app = Application()
app.add_routes(routes.routes)
run_app(app)