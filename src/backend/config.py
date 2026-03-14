import json

class Config:
    instance: Config

    token: str
    devs: list[int]
    name: str
    server_invite: str
    server_id: int
    bot_invite: str
    prefixes: list[str]
    database_file: str
    api_url: str
    data_path: str

    use_extras: bool
    donation: str
    user_token: str | None
    bot_client_id: int | None
    bot_bios: dict[str, str] | None

    _fields_map = {
        "token": "token",
        "devs": "devs",
        "name": "name",
        "hq_server_invite": "server_invite",
        "hq_server_id": "server_id",
        "bot_invite_link": "bot_invite",
        "prefixes": "prefixes",
        "database": "database_file",
        "api": "api_url",
        "data": "data_path",
        "use_extras": "use_extras",
        "?donation": "donation",
        "?user_token": "user_token",
        "?client_id": "bot_client_id",
        "?bio": "bot_bios",
    }

    def __init__(self, filename: str = "config.json"):
        with open(filename) as f:
            conf = json.loads(f.read())
            for k, v in self._fields_map.items():
                optional = False
                if k.startswith("?"):
                    k = k[1:]
                    optional = True
                if k in conf:
                    setattr(self, v, conf[k])
                elif not optional:
                    raise KeyError(f"Cannot find key {k!r} in config.json!")
                else:
                    setattr(self, v, None)

        Config.instance = self
