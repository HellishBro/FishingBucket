import uvicorn
from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.params import Header

from .api_database import Database, Session
from .context import ApplicationContext

async def require_session(authorization: str | None = Header(None)) -> Session:
    if not authorization:
        raise HTTPException(401, "Missing AUTHORIZATION header.")

    session = await Database.instance.get_session(authorization)
    if not session:
        raise HTTPException(401, "Invalid or expired session.")

    return session

class Application:
    def __init__(self):
        self.app = FastAPI()
        self.context: ApplicationContext = None
        self.ready = False
        self.server: uvicorn.Server = None
        self.routers: list[APIRouter] = []

    def set_context(self, context: ApplicationContext):
        self.context = context
        self.ready = True
        Database(self.context.config.api_server.database)

    def create_router(self, prefix: str) -> APIRouter:
        r = APIRouter(prefix=prefix)
        self.routers.append(r)
        return r

    async def serve(self):
        if not self.ready:
            raise Exception("Application is not ready yet!")

        await Database.instance.init()
        config = self.context.config

        for r in self.routers:
            self.app.include_router(r)

        host, port = config.api_server.domain, config.api_server.port
        config = uvicorn.Config(self.app, host, port)
        self.server = uvicorn.Server(config)
        await self.server.serve()
        print(f"API server is running at {host}:{port}!")

    async def close(self):
        if self.server:
            self.server.should_exit = True
            await self.server.shutdown()
        self.ready = False
