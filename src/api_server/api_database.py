import datetime
from dataclasses import dataclass
import aiosqlite as sql
import json
import secrets

from ..backend.cache import TTLCache


@dataclass
class Session:
    session_id: str
    user_id: int
    data: dict
    created: float
    expires: float

class Cache:
    sessions = TTLCache[str, Session](4096, 3600)

SESSION_TTL = 3600 * 24

def this_time() -> float:
    return datetime.datetime.now().timestamp()


class Database:
    instance: Database

    def __init__(self, database_file: str = "../api_database.db"):
        Database.instance = self
        self.connection: sql.Connection = None
        self.database_file = database_file

    async def init(self):
        self.connection = await sql.connect(self.database_file)
        await self.create_tables()
        print("API database connection established.")

    async def create_tables(self):
        await self.connection.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            data TEXT,
            created REAL,
            expires REAL
        )
        """)
        await self.connection.execute("CREATE INDEX IF NOT EXISTS idx_session_ids ON sessions (id)")
        await self.connection.commit()

    async def get_session(self, session_id: str) -> Session | None:
        if ret := Cache.sessions.get(session_id):
            return ret

        async with self.connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id, )) as cursor:
            res = await cursor.fetchone()
            if not res: return None
            sess = Session(res[0], res[1], json.loads(res[2]), res[3], res[4])
            now = this_time()
            if now > sess.expires:
                await self.connection.execute("DELETE FROM sessions WHERE id = ?", (session_id, ))
                await self.connection.commit()
                Cache.sessions.invalidate(session_id)
                return None
            new_expires = now + SESSION_TTL
            await self.connection.execute("UPDATE sessions SET expires = ? WHERE id = ?", (new_expires, session_id))
            await self.connection.commit()
            sess.expires = new_expires
            Cache.sessions.set(session_id, sess)
            return sess

    async def new_session(self, user_id: int, data: dict) -> str:
        session_id = secrets.token_hex(64)
        now = this_time()
        await self.connection.execute(
            "INSERT INTO sessions (id, user_id, data, created, expires) VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, json.dumps(data), now, now + SESSION_TTL)
        )
        await self.connection.commit()
        return session_id
