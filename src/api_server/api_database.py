import datetime
from dataclasses import dataclass
from pathlib import Path

import aiosqlite as sql
import json
import secrets

from ..backend.cache import TTLCache
from ..backend.models import Platform


@dataclass
class Session:
    session_id: str
    user_id: int
    data: dict
    created: float
    expires: float
    platform: Platform

class Cache:
    sessions: TTLCache[str, Session] = TTLCache(4096, 3600)

SESSION_TTL = 3600 * 24

def this_time() -> float:
    return datetime.datetime.now().timestamp()


class Database:
    instance: Database

    def __init__(self, database_file: Path | str = "../api_database.db"):
        Database.instance = self
        self.connection: sql.Connection = None
        self.database_file = database_file

    async def init(self):
        self.connection = await sql.connect(self.database_file)
        await self.create_tables()
        await self.migrate()
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
        await self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS meta (
            db_version INTEGER
        );
        INSERT INTO meta (db_version) SELECT 0 WHERE NOT EXISTS (SELECT 0 FROM meta);
        """)
        await self.connection.execute("CREATE INDEX IF NOT EXISTS idx_session_ids ON sessions (id)")
        await self.connection.commit()

    async def migrate(self):
        try:
            async with self.connection.execute("SELECT db_version FROM meta LIMIT 1;") as cursor:
                version: int = (await cursor.fetchone())[0]
        except sql.DatabaseError as e:
            print(e)
            version = 0

        if version == 0:
            await self.connection.executescript("""
            ALTER TABLE sessions ADD COLUMN platform_type INTEGER;
            CREATE TABLE IF NOT EXISTS meta (
                db_version INTEGER
            );
            INSERT INTO meta (db_version) VALUES (1);
            """)
            version += 1

        async with self.connection.execute("UPDATE meta SET db_version = ?", (version, )): pass


    async def get_session(self, session_id: str) -> Session | None:
        if ret := Cache.sessions.get(session_id):
            return ret

        async with self.connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id, )) as cursor:
            res = await cursor.fetchone()
            if not res: return None
            sess = Session(res[0], res[1], json.loads(res[2]), res[3], res[4], Platform.from_(res[5]))
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

    async def new_session(self, user_id: int, data: dict, platform: Platform) -> str:
        session_id = secrets.token_hex(64)
        now = this_time()
        await self.connection.execute(
            "INSERT INTO sessions (id, user_id, data, created, expires, platform_type) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, user_id, json.dumps(data), now, now + SESSION_TTL, platform.get())
        )
        await self.connection.commit()
        return session_id

    async def remove_all_sessions(self, user_id: int):
        async with self.connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id, )):
            Cache.sessions.clear(lambda k, v: v.user_id == user_id)
