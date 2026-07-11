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
    current_form TEXT,
    pronouns TEXT
);

CREATE TABLE IF NOT EXISTS proxy_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    description TEXT,
    owner INTEGER,
    creation_date REAL,
    tag TEXT,
    parent INTEGER
);

CREATE TABLE IF NOT EXISTS channel_webhook_map (
    channel_id INTEGER,
    webhook_id INTEGER,
    guild_type INTEGER,
    PRIMARY KEY (channel_id, guild_type)
);

CREATE TABLE IF NOT EXISTS global_stats (
    key TEXT PRIMARY KEY,
    value REAL
);
INSERT OR IGNORE INTO global_stats (key, value) VALUES ('version', 14);

CREATE TABLE IF NOT EXISTS permission_overrides (
    id INTEGER,
    guild_id INTEGER,
    allow_proxy INTEGER,
    id_type INTEGER,
    guild_type INTEGER,
    PRIMARY KEY (id, guild_id, guild_type)
); -- 0 - channel; 1 - role; 2 - user

CREATE TABLE IF NOT EXISTS guild_preferences (
    guild_id INTEGER,
    disallow_by_default BOOLEAN,
    logging_channel INTEGER,
    dice_functions BLOB,
    guild_type INTEGER,
    PRIMARY KEY (guild_id, guild_type)
);

CREATE TABLE IF NOT EXISTS message_links (
    message_id INTEGER,
    channel_id INTEGER,
    proxy_id INTEGER,
    platform_user INTEGER,
    platform_type INTEGER
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY,
    private_description BOOLEAN,
    private_trigger BOOLEAN,
    private_metadata BOOLEAN,
    private_group BOOLEAN,
    private_list BOOLEAN,
    private_forms BOOLEAN,
    dice_functions BLOB,
    private_pronouns BOOLEAN
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT
);

CREATE TABLE IF NOT EXISTS accounts (
    user_id INTEGER,
    account_type INTEGER,
    owner INTEGER NOT NULL,
    PRIMARY KEY (user_id, account_type),
    FOREIGN KEY (owner) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS autoproxies (
    guild_id INTEGER,
    user_id INTEGER,
    proxy INTEGER,
    last_used_proxy INTEGER,
    expires REAL,
    guild_type INTEGER,
    PRIMARY KEY (guild_id, user_id, guild_type)
);

CREATE INDEX IF NOT EXISTS idx_proxies_owner ON proxies (owner);
CREATE INDEX IF NOT EXISTS idx_proxies_group ON proxies (proxy_group);
CREATE INDEX IF NOT EXISTS idx_message_links_channel ON message_links (channel_id);
CREATE INDEX IF NOT EXISTS idx_message_links_proxy ON message_links (proxy_id);
CREATE INDEX IF NOT EXISTS idx_permission_overrides_guild ON permission_overrides (guild_id);
CREATE INDEX IF NOT EXISTS idx_permission_overrides_id ON permission_overrides (id);
CREATE INDEX IF NOT EXISTS idx_autoproxies_guild_id ON autoproxies (guild_id);
CREATE INDEX IF NOT EXISTS idx_autoproxies_user_id ON autoproxies (user_id);
CREATE INDEX IF NOT EXISTS idx_accounts_query ON accounts (user_id, account_type);
CREATE INDEX IF NOT EXISTS idx_group_parent ON proxy_groups (id, parent);