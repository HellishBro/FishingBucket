import json
from typing import Any
import aiosqlite as sql
import time
from collections import namedtuple
from dataclasses import dataclass

from .cache import TTLCache
from .models import Proxy, ProxyGroup

lst_proxy_fields = ["id", "name", "description", "avatar_url", "trigger", "owner", "times_used", "creation_date", "proxy_group", "nickname", "proxy_forms", "current_form"]
proxy_fields = ", ".join(lst_proxy_fields)
group_fields = ", ".join(["id", "name", "description", "owner", "creation_date", "tag", "parent"])

def upsert_query(table: str, key: str, key_check: Any, names: dict[str, tuple[Any, Any]], changes: list[str], values: list[Any]) -> tuple[str, tuple[Any]]:
    cols = list(names.keys())
    defaults = [t[1] if t[0] is None else t[0] for t in names.values()]
    placeholders = ", ".join(["?"] * (1 + len(cols)))
    col_list = ", ".join(cols)
    update_parts = ", ".join(
        f"{k} = ?" if k in changes else f"{k} = {k}"
        for k in cols
    )
    sql_str = (
        f"INSERT INTO {table} ({key}, {col_list}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT({key}) DO UPDATE SET {update_parts} "
        f"WHERE {key} = ?"
    )
    params = (key_check, ) + tuple(defaults) + tuple(values) + (key_check, )
    return sql_str, params

class UserPreference(namedtuple("UserPreference", "private_description private_trigger private_metadata private_group private_list private_forms dice_functions")):
    private_description: bool
    private_trigger: bool
    private_metadata: bool
    private_group: bool
    private_list: bool
    private_forms: bool
    dice_functions: bytes

class GuildPreference(namedtuple("GuildPreference", "disallow_by_default logging_channel dice_functions")):
    disallow_by_default: bool
    logging_channel: int
    dice_functions: bytes

@dataclass # it's better if this is mutable for caching
class UserAutoproxyPreference:
    proxy: int | None
    last_used_proxy: int | None
    expires: float

    def expires_now(self) -> bool:
        return self.expires != 0 and self.expires < time.time()

class Cache:
    LONG = 3600
    MEDIUM = 600
    SHORT = 60

    MID = 1024
    BIG = 2048
    MASSIVE = 4096
    SMALL = 512

    proxy_cache = TTLCache[int, Proxy](MASSIVE, LONG)
    group_cache = TTLCache[int, ProxyGroup](MASSIVE, LONG)

    user_id = TTLCache[tuple[int], int](MID, LONG)
    user_preferences = TTLCache[tuple[int], UserPreference](MID, LONG)
    autoproxy_preferences = TTLCache[tuple[int, int], UserAutoproxyPreference | None](MID, LONG)
    latest_proxy_message_from_user = TTLCache[tuple[int, int], int](BIG, SHORT)
    proxy_id_from_message = TTLCache[tuple[int, int], int](MID, MEDIUM)
    guild_preferences = TTLCache(SMALL, MEDIUM)
    guild_allows = TTLCache(SMALL, LONG)
    guild_role_allows = TTLCache[int, tuple[tuple[int, bool | None]]](MID, LONG)
    permission_allows: list[TTLCache[tuple[int, int], bool]] = [TTLCache(MEDIUM, LONG), TTLCache(MEDIUM, LONG), TTLCache(MEDIUM, LONG)]
    webhook_link = TTLCache(MEDIUM, LONG)
    proxies_from_user = TTLCache[int, list[int]](BIG, MEDIUM)
    groups_from_user = TTLCache[int, list[int]](MEDIUM, MEDIUM)


class Database:
    instance: Database

    def __init__(self, database_file: str = "../database.db"):
        Database.instance = self
        self.connection: sql.Connection = None
        self.database_file = database_file

    async def init(self):
        self.connection = await sql.connect(self.database_file)
        await self.create_tables()
        await self.migrate()
        await self.connection.execute("VACUUM")
        await self.connection.commit()
        print("Database connection established.")

    async def create_tables(self):
        await self.connection.execute("""
        CREATE TABLE IF NOT EXISTS proxies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            avatar_url TEXT NOT NULL,
            trigger TEXT NOT NULL,
            owner INTEGER NOT NULL,
            times_used INTEGER,
            creation_date REAL,
            proxy_group INTEGER,
            nickname TEXT,
            proxy_forms TEXT,
            current_form TEXT
        );
        """)
        await self.connection.execute("""
        CREATE TABLE IF NOT EXISTS proxy_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            owner INTEGER,
            creation_date REAL,
            tag TEXT,
            parent INTEGER
        );
        """)
        await self.connection.execute("""
        CREATE TABLE IF NOT EXISTS channel_webhook_map (
            channel_id INTEGER PRIMARY KEY,
            webhook_id INTEGER
        );
        """)
        await self.connection.execute("""
        CREATE TABLE IF NOT EXISTS global_stats (
            key TEXT PRIMARY KEY,
            value REAL
        );
        """)
        await self.connection.execute("""
        CREATE TABLE IF NOT EXISTS permission_overrides (
            id INTEGER,
            guild_id INTEGER,
            allow_proxy INTEGER,
            id_type INTEGER,
            PRIMARY KEY (id, guild_id)
        );
        """) # 0 - channel; 1 - role; 2 - user
        await self.connection.execute("""
        CREATE TABLE IF NOT EXISTS guild_preferences (
            guild_id INTEGER PRIMARY KEY,
            disallow_by_default BOOLEAN,
            logging_channel INTEGER,
            dice_functions BLOB
        );
        """)
        await self.connection.execute("""
        CREATE TABLE IF NOT EXISTS message_links (
            message_id INTEGER,
            channel_id INTEGER,
            proxy_id INTEGER
        );
        """)
        await self.connection.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            private_description BOOLEAN,
            private_trigger BOOLEAN,
            private_metadata BOOLEAN,
            private_group BOOLEAN,
            private_list BOOLEAN,
            private_forms BOOLEAN,
            dice_functions BLOB
        );
        """)
        await self.connection.execute("""
        CREATE TABLE IF NOT EXISTS alt_accounts (
            alt_id INTEGER PRIMARY KEY,
            owner INTEGER
        );
        """)
        await self.connection.execute("""
        CREATE TABLE IF NOT EXISTS autoproxies (
            guild_id INTEGER,
            user_id INTEGER,
            proxy INTEGER,
            last_used_proxy INTEGER,
            expires REAL,
            PRIMARY KEY (guild_id, user_id)
        );
        """)
        await self.connection.execute("CREATE INDEX IF NOT EXISTS idx_proxies_owner ON proxies (owner);")
        await self.connection.execute("CREATE INDEX IF NOT EXISTS idx_proxies_group ON proxies (proxy_group);")
        await self.connection.execute("CREATE INDEX IF NOT EXISTS idx_message_links_channel ON message_links (channel_id);")
        await self.connection.execute("CREATE INDEX IF NOT EXISTS idx_message_links_proxy ON message_links (proxy_id);")
        await self.connection.execute("CREATE INDEX IF NOT EXISTS idx_permission_overrides_guild ON permission_overrides (guild_id);")
        await self.connection.execute("CREATE INDEX IF NOT EXISTS idx_permission_overrides_id ON permission_overrides (id);")
        await self.connection.execute("CREATE INDEX IF NOT EXISTS idx_autoproxies_guild_id ON autoproxies (guild_id);")
        await self.connection.execute("CREATE INDEX IF NOT EXISTS idx_autoproxies_user_id ON autoproxies (user_id);")
        await self.connection.execute("PRAGMA journal_mode=WAL;")
        await self.connection.execute("PRAGMA synchronous=NORMAL;")
        await self.connection.execute("PRAGMA cache_size=-64000;") # 64MB cache
        await self.connection.execute("PRAGMA temp_store=MEMORY;")
        await self.connection.execute("PRAGMA mmap_size=268435456;") # 256MB mmap io
        await self.connection.commit()

    async def migrate(self):
        version = (await self.get_global_stats()).get("version", 0)

        if version == 0:
            try:
                await self.connection.execute("ALTER TABLE user_settings DROP COLUMN autoproxy")
                await self.connection.execute("ALTER TABLE user_settings DROP COLUMN autoproxy_id")
                await self.connection.execute("ALTER TABLE user_settings DROP COLUMN last_used_proxy")
            except:
                pass
            finally:
                await self.connection.commit()
            version += 1

        if version == 1:
            try:
                await self.connection.execute("ALTER TABLE proxies ADD COLUMN proxy_forms TEXT")
                await self.connection.execute("ALTER TABLE proxies ADD COLUMN current_form TEXT")
            except:
                pass
            finally:
                await self.connection.commit()
            version += 1

        if version == 2:
            try:
                await self.connection.execute("""
                CREATE TABLE IF NOT EXISTS user_settings_new (
                    user_id INTEGER PRIMARY KEY,
                    private_description BOOLEAN,
                    private_trigger BOOLEAN,
                    private_metadata BOOLEAN,
                    private_group BOOLEAN,
                    private_list BOOLEAN,
                    private_forms BOOLEAN,
                    dice_functions BLOB
                );
                """)
                await self.connection.execute("""
                INSERT INTO user_settings_new (
                    user_id,
                    private_description,
                    private_trigger,
                    private_metadata,
                    private_group,
                    private_list,
                    private_forms,
                    dice_functions
                ) SELECT 
                    user_id,
                    private_description,
                    private_trigger,
                    private_metadata,
                    private_group,
                    private_list,
                    FALSE,
                    dice_functions
                FROM user_settings;
                """)
                await self.connection.execute("""
                DROP TABLE user_settings;
                """)
                await self.connection.execute("""
                ALTER TABLE user_settings_new RENAME TO user_settings;
                """)
            except:
                pass
            finally:
                await self.connection.commit()

            version += 1

        if version == 3:
            try:
                await self.connection.execute("""
                ALTER TABLE channel_overrides RENAME TO permission_overrides;
                """)
                await self.connection.execute("""
                ALTER TABLE permission_overrides RENAME COLUMN channel_id TO id;
                """)
                await self.connection.execute("""
                ALTER TABLE permission_overrides ADD COLUMN id_type INTEGER;
                """)
            except:
                pass
            finally:
                await self.connection.commit()
            version += 1

        if version == 4:
            try:
                await self.connection.execute("""
                CREATE TABLE IF NOT EXISTS permission_overrides_new (
                    id INTEGER,
                    guild_id INTEGER,
                    allow_proxy INTEGER,
                    id_type INTEGER,
                    PRIMARY KEY (id, guild_id)
                );
                """)
                await self.connection.execute("""
                INSERT INTO permission_overrides_new (
                    id,
                    guild_id,
                    allow_proxy,
                    id_type
                ) SELECT
                    id,
                    guild_id,
                    allow_proxy,
                    id_type
                FROM permission_overrides;
                """)
                await self.connection.execute("""
                DROP TABLE permission_overrides;
                """)
                await self.connection.execute("""
                ALTER TABLE permission_overrides_new RENAME TO permission_overrides;
                """)
            except:
                pass
            finally:
                await self.connection.commit()
            version += 1

        await self.set_global_data("version", str(version), version)

    @Cache.user_id.cache_async()
    async def get_user_id(self, alt_or_user: int) -> int:
        async with self.connection.execute("SELECT COALESCE((SELECT owner FROM alt_accounts WHERE alt_id = ?), ?)", (alt_or_user, alt_or_user)) as cursor:
            return (await cursor.fetchone())[0]

    async def link_accounts(self, owner: int, alt: int):
        await self.connection.execute("INSERT INTO alt_accounts (alt_id, owner) VALUES (?, ?)", (alt, owner))
        await self.connection.commit()

    async def unlink_account(self, alt: int):
        await self.connection.execute("DELETE FROM alt_accounts WHERE alt_id = ?", (alt, ))
        await self.connection.commit()
        Cache.user_id.invalidate((alt, ))

    async def get_autoproxy_preference(self, user_id: int, guild_id: int) -> UserAutoproxyPreference | None:
        if (ref := Cache.autoproxy_preferences.get((user_id, guild_id), 0)) is not 0:
            if ref and ref.expires_now():
                Cache.autoproxy_preferences.invalidate((user_id, guild_id))
                return None
            return ref

        async with self.connection.execute(
            "SELECT proxy, last_used_proxy, expires FROM autoproxies WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                if guild_id != 0:
                    return await self.get_autoproxy_preference(user_id, 0)
                Cache.autoproxy_preferences.set((user_id, guild_id), None)
                return None
            preferences = UserAutoproxyPreference(*row)
            if preferences.expires_now():
                await self.remove_autoproxy_preference(user_id, guild_id)
                if guild_id != 0:
                    return await self.get_autoproxy_preference(user_id, 0)
                return None
            Cache.autoproxy_preferences.set((user_id, guild_id), preferences)
            return preferences

    async def set_autoproxy_preference(self, user_id: int, guild_id: int, proxy: int | None, expires: int | None):
        await self.connection.execute(
            "INSERT OR REPLACE INTO autoproxies (guild_id, user_id, proxy, last_used_proxy, expires) VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, proxy, None, (time.time() + expires) if expires else 0)
        )
        await self.connection.commit()
        Cache.autoproxy_preferences.invalidate((user_id, guild_id))

    async def set_autoproxy_last_used_proxy(self, user_id: int, guild_id: int, last_used_proxy: int):
        await self.connection.execute(
            "UPDATE autoproxies SET last_used_proxy = ? WHERE guild_id = ? AND user_id = ?",
            (last_used_proxy, guild_id, user_id)
        )
        await self.connection.commit()
        if pref := await self.get_autoproxy_preference(user_id, guild_id):
            pref.last_used_proxy = last_used_proxy

    async def remove_autoproxy_preference(self, user_id: int, guild_id: int):
        await self.connection.execute("DELETE FROM autoproxies WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        await self.connection.commit()
        Cache.autoproxy_preferences.invalidate((user_id, guild_id))

    async def remove_all_autoproxy_preference(self, user_id: int):
        await self.connection.execute("DELETE FROM autoproxies WHERE user_id = ?", (user_id, ))
        await self.connection.commit()
        Cache.autoproxy_preferences.clear(lambda k, v: k[0] == user_id)

    async def set_user_preferences(
            self,
            user_id: int,
            private_description: bool | None = None,
            private_trigger: bool | None = None,
            private_metadata: bool | None = None,
            private_group: bool | None = None,
            private_list: bool | None = None,
            private_forms: bool | None = None,
            dice_functions: bytes | None = None
    ):
        names = {
            "private_description": (private_description, False),
            "private_trigger": (private_trigger, False),
            "private_metadata": (private_metadata, False),
            "private_group": (private_group, False),
            "private_list": (private_list, False),
            "private_forms": (private_forms, False),
            "dice_functions": (dice_functions, b"")
        }
        changes = [k for k, (v, _) in names.items() if v is not None]
        values = [v for v, _ in names.values() if v is not None]

        if not changes:
            return

        user_id = await self.get_user_id(user_id)
        prefs = await self.get_user_preferences(user_id)
        true_compare_list = (private_description, private_trigger, private_metadata, private_group, private_list, private_forms, dice_functions)
        true_compare_list = tuple((a if a is not None else b for a, b in zip(true_compare_list, prefs)))
        if prefs != true_compare_list:
            await self.connection.execute(*upsert_query("user_settings", "user_id", user_id, names, changes, values))
            await self.connection.commit()
            Cache.user_preferences.invalidate((user_id, ))

    @Cache.user_preferences.cache_async()
    async def get_user_preferences(self, user_id: int) -> UserPreference:
        async with self.connection.execute(
                "SELECT * FROM user_settings WHERE user_id = ?",
                (await self.get_user_id(user_id), )
        ) as cursor:
            res = await cursor.fetchone()
            if not res: return UserPreference(False, False, False, False, False, False, b"")
            else: return UserPreference(*res[1:])

    @Cache.latest_proxy_message_from_user.cache_async()
    async def get_latest_proxy_message_from_user(self, channel_id: int, owner: int) -> int | None:
        async with self.connection.execute(
            "SELECT ml.message_id FROM message_links ml JOIN proxies p ON ml.proxy_id = p.id WHERE ml.channel_id = ? AND p.owner = ? ORDER BY ml.message_id DESC LIMIT 1",
            (channel_id, owner)
        ) as cursor:
            res = await cursor.fetchone()
            if not res: return None
            message_id, = res
            return message_id

    async def link_message(self, message_id: int, channel_id: int, proxy_id: int):
        await self.connection.execute(
            "INSERT INTO message_links (message_id, channel_id, proxy_id) VALUES (?, ?, ?)",
            (message_id, channel_id, proxy_id)
        )
        await self.connection.commit()

    async def delete_link_message(self, message_id: int, channel_id: int):
        prox_id = await self.get_proxy_id(message_id, channel_id)
        if prox_id:
            proxy = await self.get_proxy(prox_id)
            owner = proxy.owner
            Cache.latest_proxy_message_from_user.invalidate((channel_id, owner))
        await self.connection.execute(
            "DELETE FROM message_links WHERE message_id = ? AND channel_id = ?",
            (message_id, channel_id)
        )
        await self.connection.commit()

    @Cache.proxy_id_from_message.cache_async()
    async def get_proxy_id(self, message_id: int, channel_id: int) -> int | None:
        async with self.connection.execute(
            "SELECT proxy_id FROM message_links WHERE message_id = ? AND channel_id = ?",
            (message_id, channel_id)
        ) as cursor:
            res = await cursor.fetchone()
            if not res: return None
            return res[0]

    async def override_permission(self, id_: int, guild_id: int, allow_proxy: str, id_type: int):
        allow_proxy_enum = {"allow": 1, "disallow": -1, "default": 0}[allow_proxy]
        await self.connection.execute(
            "INSERT INTO permission_overrides (id, guild_id, allow_proxy, id_type) VALUES (?, ?, ?, ?) ON CONFLICT(id, guild_id) DO UPDATE SET allow_proxy = ? WHERE id = ?",
            (id_, guild_id, allow_proxy_enum, id_type, allow_proxy_enum, id_)
        )
        await self.connection.commit()
        Cache.guild_allows.invalidate((guild_id, id_type))
        Cache.permission_allows[id_type].invalidate((id_, guild_id))
        if id_type == 1:
            Cache.guild_role_allows.invalidate(guild_id)

    async def remove_all_overrides(self, guild_id: int):
        await self.connection.execute(
            "DELETE FROM permission_overrides WHERE guild_id = ?",
            (guild_id,)
        )
        await self.connection.commit()
        for id_type in range(3):
            Cache.permission_allows[id_type].clear(lambda key, val: key[1] == guild_id)
            Cache.guild_allows.invalidate((guild_id, id_type))
            if id_type == 1:
                Cache.guild_role_allows.invalidate(guild_id)

    async def set_guild_preferences(self, guild_id: int, disallow_by_default: bool | None = None, logging_channel: int | None = None, dice_functions: bytes | None = None):
        names = {
            "disallow_by_default": (disallow_by_default, False),
            "logging_channel": (logging_channel, 0),
            "dice_functions": (dice_functions, b"")
        }
        changes = [k for k, (v, _) in names.items() if v is not None]
        values = [v for v, _ in names.values() if v is not None]

        if not changes:
            return

        prefs = await self.get_guild_preferences(guild_id)
        true_compare_list = (disallow_by_default, logging_channel, dice_functions)
        true_compare_list = tuple((a if a is not None else b for a, b in zip(true_compare_list, prefs)))
        if prefs != true_compare_list:
            await self.connection.execute(*upsert_query("guild_preferences", "guild_id", guild_id, names, changes, values))
            await self.connection.commit()
            Cache.guild_preferences.invalidate((guild_id, ))
            Cache.guild_role_allows.invalidate(guild_id)
            for i in range(3):
                Cache.permission_allows[i].clear(lambda k, v: k[1] == guild_id)
                Cache.guild_allows.invalidate((guild_id, i))

    @Cache.guild_preferences.cache_async()
    async def get_guild_preferences(self, guild_id: int) -> GuildPreference:
        async with self.connection.execute(
            "SELECT * FROM guild_preferences WHERE guild_id = ?", (guild_id, )
        ) as cursor:
            res = await cursor.fetchone()
            if not res: return GuildPreference(False, 0, b"")
            return GuildPreference(*res[1:])

    @Cache.guild_allows.cache_async()
    async def get_guild_overrides(self, guild_id: int, id_type: int) -> dict[int, str]:
        async with self.connection.execute(
            "SELECT id, allow_proxy FROM permission_overrides WHERE guild_id = ? AND id_type = ?",
            (guild_id, id_type)
        ) as cursor:
            res = await cursor.fetchall()
            if not res: return {}
            d = {}
            for cid, allow in res:
                d[cid] = {-1: "disallow", 0: "default", 1: "allow"}[allow]
            return d

    async def get_allow_proxy(self, channel_id: int, guild_id: int, role_ids: list[int], user_id: int) -> bool:
        channel_allowed = None
        guild_allowed = None
        roles_allowed = None
        user_allowed = None

        if (channel_allowed := Cache.permission_allows[0].get((channel_id, guild_id))) is None:
            async with self.connection.execute(
                "SELECT allow_proxy FROM permission_overrides WHERE id = ? AND id_type = 0",
                (channel_id,)
            ) as cursor: # channel
                res = await cursor.fetchone()
                if res:
                    allow, = res
                    if allow in (-1, 1):
                        channel_allowed = allow == 1
                        Cache.permission_allows[0].set((channel_id, guild_id), channel_allowed)

        if channel_allowed is None:
            guild_allowed = not (await self.get_guild_preferences(guild_id)).disallow_by_default

        if (all_role_allows := Cache.guild_role_allows.get(guild_id)) is None:
            async with self.connection.execute(
                "SELECT id, allow_proxy FROM permission_overrides WHERE guild_id = ? AND id_type = 1",
                (guild_id,)
            ) as cursor: # roles
                pairs = []
                for res in await cursor.fetchall():
                    rid, allow = res
                    if allow in (-1, 1):
                        pairs.append((rid, allow == 1))
                    else:
                        pairs.append((rid, None))
                all_role_allows = tuple(pairs)
                Cache.guild_role_allows.set(guild_id, all_role_allows)

        m = dict(all_role_allows)
        allowed = [m[role] for role in role_ids if m.get(role) is not None]
        if allowed:
            roles_allowed = allowed[-1]

        if (user_allowed := Cache.permission_allows[2].get((user_id, guild_id))) is None:
            async with self.connection.execute(
                "SELECT allow_proxy FROM permission_overrides WHERE id = ? AND guild_id = ? AND id_type = 2",
                (user_id, guild_id)
            ) as cursor: # user
                res = await cursor.fetchone()
                if res:
                    allow, = res
                    if allow in (-1, 1):
                        user_allowed = allow == 1
                        Cache.permission_allows[2].set((user_id, guild_id), user_allowed)

        resolution = [guild_allowed, channel_allowed, roles_allowed, user_allowed]
        resolution = [res for res in resolution if res is not None]
        if resolution: return resolution[-1]
        return True

    async def put_channel_webhook_link(self, channel_id: int, webhook_id: int):
        await self.connection.execute(
            "INSERT INTO channel_webhook_map (channel_id, webhook_id) VALUES (?, ?)",
            (channel_id, webhook_id)
        )
        Cache.webhook_link.invalidate((channel_id, ))
        await self.connection.commit()

    @Cache.webhook_link.cache_async()
    async def get_channel_webhook(self, channel_id: int) -> int | None:
        async with self.connection.execute(
            "SELECT webhook_id FROM channel_webhook_map WHERE channel_id = ?",
            (channel_id, )
        ) as cursor:
            res = await cursor.fetchone()
            return res[0] if res else None

    async def put_proxy(self, proxy: Proxy) -> Proxy:
        cursor = await self.connection.execute(
            "INSERT INTO proxies (name, description, avatar_url, trigger, owner, times_used, creation_date, proxy_group, nickname, proxy_forms, current_form) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (proxy.name, proxy.description, proxy.avatar_url, "\n".join(proxy.triggers), proxy.owner, proxy.times_used, time.time(), proxy.group.id if proxy.group else None, proxy.nickname, json.dumps(proxy.forms), proxy.current_form)
        )
        await self.connection.commit()
        proxy.id = cursor.lastrowid
        Cache.proxies_from_user.invalidate(proxy.owner)
        await cursor.close()

        await self.set_global_data("total_proxies", "value + 1", 1)

        return proxy

    async def put_group(self, group: ProxyGroup) -> ProxyGroup:
        cursor = await self.connection.execute(
            "INSERT INTO proxy_groups (name, description, owner, creation_date, tag, parent) VALUES (?, ?, ?, ?, ?, ?)",
            (group.name, group.description, group.owner, group.creation_date, group.tag, group.parent.id if group.parent else None)
        )
        await self.connection.commit()

        group.id = cursor.lastrowid
        Cache.groups_from_user.invalidate(group.owner)
        await cursor.close()

        return group

    async def use_proxy(self, id_: int):
        await self.connection.execute(
            "UPDATE proxies SET times_used = times_used + 1 WHERE id = ?",
            (id_, )
        )
        if prox := await self.get_proxy(id_):
            prox.times_used += 1
        await self.set_global_data("proxy_uses", "value + 1", 1)

    async def transfer_proxy_usage(self, old_id: int, new_id: int):
        await self.connection.execute(
            "UPDATE proxies SET times_used = times_used - 1 WHERE id = ?",
            (old_id,)
        )
        await self.connection.execute(
            "UPDATE proxies SET times_used = times_used + 1 WHERE id = ?",
            (new_id,)
        )
        if prox := await self.get_proxy(old_id):
            prox.times_used -= 1
        if prox := await self.get_proxy(new_id):
            prox.times_used += 1
        await self.connection.commit()

    async def update_avatar(self, id_: int, avatar_url: str):
        await self.connection.execute(
            "UPDATE proxies SET avatar_url = ? WHERE id = ?",
            (avatar_url, id_)
        )
        if prox := await self.get_proxy(id_):
            prox.avatar_url = avatar_url
        await self.connection.commit()

    async def update_group(self, proxy_id: int, group_id: int | None):
        await self.connection.execute(
            "UPDATE proxies SET proxy_group = ? WHERE id = ?",
            (group_id, proxy_id)
        )
        if prox := await self.get_proxy(proxy_id):
            prox.group = await self.get_group(group_id)
        await self.connection.commit()

    async def update_description(self, proxy_id: int, description: str):
        await self.connection.execute(
            "UPDATE proxies SET description = ? WHERE id = ?",
            (description, proxy_id)
        )
        if prox := await self.get_proxy(proxy_id):
            prox.description = description
        await self.connection.commit()

    async def update_trigger(self, id_: int, triggers: list[str]):
        await self.connection.execute(
            "UPDATE proxies SET trigger = ? WHERE id = ?",
            ("\n".join(triggers), id_)
        )
        if prox := await self.get_proxy(id_):
            prox.triggers = triggers
        await self.connection.commit()

    async def update_forms(self, id_: int, forms: dict[str, str]):
        await self.connection.execute(
            "UPDATE proxies SET proxy_forms = ? WHERE id = ?",
            (json.dumps(forms), id_)
        )
        if prox := await self.get_proxy(id_):
            prox.forms = forms
        await self.connection.commit()

    async def update_current_form(self, id_: int, form: str | None):
        await self.connection.execute(
            "UPDATE proxies SET current_form = ? WHERE id = ?",
            (form, id_)
        )
        if prox := await self.get_proxy(id_):
            prox.current_form = form
        await self.connection.commit()

    async def update_name(self, id_: int, name: str):
        await self.connection.execute(
            "UPDATE proxies SET name = ? WHERE id = ?",
            (name, id_)
        )
        if prox := await self.get_proxy(id_):
            prox.name = name
        await self.connection.commit()

    async def update_nickname(self, id_: int, nickname: str):
        await self.connection.execute(
            "UPDATE proxies SET nickname = ? WHERE id = ?",
            (nickname, id_)
        )
        if prox := await self.get_proxy(id_):
            prox.nickname = nickname
        await self.connection.commit()

    async def update_group_name(self, id_: int, name: str):
        await self.connection.execute(
            "UPDATE proxy_groups SET name = ? WHERE id = ?",
            (name, id_)
        )
        if group := await self.get_group(id_):
            group.name = name
        await self.connection.commit()

    async def update_group_tag(self, id_: int, tag: str):
        await self.connection.execute(
            "UPDATE proxy_groups SET tag = ? WHERE id = ?",
            (tag, id_)
        )
        if group := await self.get_group(id_):
            group.tag = tag
        await self.connection.commit()

    async def update_group_description(self, id_: int, desc: str):
        await self.connection.execute(
            "UPDATE proxy_groups SET description = ? WHERE id = ?",
            (desc, id_)
        )
        if group := await self.get_group(id_):
            group.description = desc
        await self.connection.commit()

    async def update_group_parent(self, id_: int, parent: int | None):
        await self.connection.execute(
            "UPDATE proxy_groups SET parent = ? WHERE id = ?",
            (parent, id_)
        )
        if group := await self.get_group(id_):
            group.parent = await self.get_group(parent)
        await self.connection.commit()

    async def delete_proxy(self, id_: int):
        prox = await self.get_proxy(id_)
        if prox:
            Cache.proxies_from_user.invalidate(prox.owner)
            await self.connection.execute(
                "DELETE FROM proxies WHERE id = ?",
                (id_, )
            )
            await self.connection.commit()
            await self.set_global_data("total_proxies", "value - 1", 0)

    async def delete_group(self, id_: int):
        group = await self.get_group(id_)
        Cache.groups_from_user.invalidate(group.owner)
        await self.connection.execute(
            "DELETE FROM proxy_groups WHERE id = ?",
            (id_, )
        )
        Cache.group_cache.invalidate(id_)
        async with self.connection.execute(
            "UPDATE proxies SET proxy_group = ? WHERE proxy_group = ? RETURNING id",
            (None, id_)
        ) as cursor:
            row_ids = await cursor.fetchall()
            for row in row_ids:
                Cache.proxy_cache.invalidate(row[0])
        async with self.connection.execute(
            "UPDATE proxy_groups SET parent = ? WHERE parent = ? RETURNING id",
            (None, id_)
        ) as cursor:
            row_ids = await cursor.fetchall()
            for row in row_ids:
                Cache.group_cache.invalidate(row[0])

    async def get_proxy(self, id_: int) -> Proxy | None:
        if ret := Cache.proxy_cache.get(id_): return ret

        async with self.connection.execute(
            f"SELECT {proxy_fields} FROM proxies WHERE id = ?",
            (id_, )
        ) as cursor:
            res = await cursor.fetchone()
            if not res:
                ret = None
            else:
                ret = Proxy.from_database(res, await self.get_user_groups(res[lst_proxy_fields.index("owner")]))
                Cache.proxy_cache.set(id_, ret)
            return ret

    async def get_group(self, id_: int) -> ProxyGroup | None:
        if ret := Cache.group_cache.get(id_): return ret

        async with self.connection.execute(
            f"SELECT {group_fields} FROM proxy_groups WHERE id = ?",
            (id_, )
        ) as cursor:
            res = await cursor.fetchone()
            if not res:
                ret = None
            else:
                parent = None
                if res[6]:
                    parent = await self.get_group(res[6])

                ret = ProxyGroup.from_database(res, parent)
                Cache.group_cache.set(id_, ret)
            return ret

    async def get_group_member_count(self, id_: int) -> int:
        cursor = await self.connection.execute(
            "SELECT COUNT(*) FROM proxies WHERE proxy_group = ?",
            (id_, )
        )
        res = await cursor.fetchone()
        await cursor.close()
        if not res: return 0
        return res[0]

    async def get_user_proxies(self, user: int) -> list[Proxy]:
        user = await self.get_user_id(user)

        if ids := Cache.proxies_from_user.get(user):
            prox = []
            for id_ in ids:
                prox.append(await self.get_proxy(id_))
            return prox

        async with self.connection.execute(
            f"SELECT id FROM proxies WHERE owner = ? ORDER BY id ASC",
            (user, )
        ) as cursor:
            proxies = [await self.get_proxy(row[0]) for row in await cursor.fetchall()]
            Cache.proxies_from_user.set(user, [prox.id for prox in proxies])
            return proxies

    async def get_user_groups(self, user: int) -> list[ProxyGroup]:
        user = await self.get_user_id(user)

        if ids := Cache.groups_from_user.get(user):
            gr = []
            for id_ in ids:
                gr.append(await self.get_group(id_))
            return gr

        async with self.connection.execute(
            f"SELECT id FROM proxy_groups WHERE owner = ? ORDER BY id ASC",
            (user, )
        ) as cursor:
            groups = [await self.get_group(row[0]) for row in await cursor.fetchall()]
            Cache.groups_from_user.set(user, [group.id for group in groups])
            return groups

    async def close(self):
        await self.connection.close()

    async def delete_data(self, owner: int):
        owner = await self.get_user_id(owner)
        cur = await self.connection.execute(
            "SELECT COUNT(*) FROM proxies WHERE owner = ?",
            (owner, )
        )
        amt, = await cur.fetchone()
        await cur.close()
        await self.connection.execute(
            "DELETE FROM proxies WHERE owner = ?",
            (owner, )
        )
        await self.connection.execute(
            "DELETE FROM proxy_groups WHERE owner = ?",
            (owner, )
        )
        Cache.proxies_from_user.invalidate(owner)
        Cache.groups_from_user.invalidate(owner)
        await self.set_global_data("total_proxies", f"value - {amt}", 0)

    async def set_global_data(self, key: str, value_exists: str, value_not_exists: float):
        await self.connection.execute(
            f"INSERT INTO global_stats (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = {value_exists} WHERE key = ?",
            (key, value_not_exists, key)
        ) # who the fuck cares about sql injection attacks? not me!
        await self.connection.commit()

    async def get_global_stats(self) -> dict[str, float]:
        cursor = await self.connection.execute("SELECT * FROM global_stats")
        d = {}
        for k, v in await cursor.fetchall():
            d[k] = v
        await cursor.close()
        return d
