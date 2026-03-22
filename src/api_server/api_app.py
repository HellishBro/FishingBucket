from typing import Callable, Awaitable

from aiohttp.web import Application as aiohttpApp, AppRunner, Response, Request, HTTPForbidden, TCPSite

from .api_database import Database, Session
from .context import ApplicationContext

class Application:
    def __init__(self):
        self.app = aiohttpApp()
        self.context: ApplicationContext = None
        self.ready = False
        self.runner = AppRunner(self.app)

    def set_context(self, context: ApplicationContext):
        self.context = context
        self.ready = True
        Database(self.context.config.api_server.database)

    async def serve(self):
        if not self.ready:
            raise Exception("Application is not ready yet!")

        await Database.instance.init()
        config = self.context.config
        host, port = config.api_server.domain, config.api_server.port
        await self.runner.setup()
        site = TCPSite(self.runner, host, port)
        await site.start()
        print("API server is running!")

    async def close(self):
        await self.runner.cleanup()
        self.ready = False

    @staticmethod
    def require_session(function: Callable[[Request, Session], Awaitable[Response]]):
        async def inner(request: Request) -> Response:
            if "Authorization" in request.headers:
                auth = request.headers["Authorization"]
            else:
                raise HTTPForbidden()

            session = await Database.instance.get_session(auth)
            if not session:
                raise HTTPForbidden()

            return await function(request, session)
        return inner
