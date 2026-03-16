import json
from aiohttp.web import Application as aiohttpApp, AppRunner, Response
from aiohttp.web_runner import TCPSite

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

    @staticmethod
    def respond_json(obj: dict) -> Response:
        return Response(body=json.dumps(obj), content_type="application/json")

    async def serve(self, host = "localhost", port = 8080):
        if not self.ready:
            raise Exception("Application is not ready yet!")
        await self.runner.setup()
        site = TCPSite(self.runner, host, port)
        await site.start()

    async def close(self):
        await self.runner.cleanup()
        self.ready = False
