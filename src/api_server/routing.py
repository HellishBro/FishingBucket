from aiohttp.web import Response, Request, AbstractRouteDef, route
from typing import Awaitable, Callable

from .api_app import Application

type HandlerType = Callable[[Request], Awaitable[Response]]

class RouteTable:
    def __init__(self, app: Application, prefix: str = ""):
        self.prefix = prefix
        self.routes: list[AbstractRouteDef] = []
        self.app = app

    def route(self, method: str, path: str, handler: HandlerType, **kwargs):
        r = route(method, ("/" + self.prefix + path).replace("//", "/"), handler, **kwargs)
        self.routes.append(r)
        self.app.app.add_routes([r])

    def get(self, path: str, **kwargs):
        def wrapper(handler: HandlerType):
            self.route("GET", path, handler, **kwargs)
        return wrapper

    def post(self, path: str, **kwargs):
        def wrapper(handler: HandlerType):
            self.route("POST", path, handler, **kwargs)
        return wrapper

    def patch(self, path: str, **kwargs):
        def wrapper(handler: HandlerType):
            self.route("PATCH", path, handler, **kwargs)
        return wrapper

    def put(self, path: str, **kwargs):
        def wrapper(handler: HandlerType):
            self.route("PUT", path, handler, **kwargs)
        return wrapper

    def delete(self, path: str, **kwargs):
        def wrapper(handler: HandlerType):
            self.route("DELETE", path, handler, **kwargs)
        return wrapper