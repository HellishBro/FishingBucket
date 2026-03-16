from aiohttp.web import Response, Request, AbstractRouteDef, route
from typing import Awaitable, Callable

type HandlerType = Callable[[Request], Awaitable[Response]]

class RouteTable:
    def __init__(self, prefix: str = ""):
        self.prefix = prefix
        self.routes: list[AbstractRouteDef] = []

    def route(self, method: str, path: str, handler: HandlerType, **kwargs):
        self.routes.append(route(method, ("/" + self.prefix + path).replace("//", "/"), handler, **kwargs))

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