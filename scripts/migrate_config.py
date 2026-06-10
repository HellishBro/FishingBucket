import json
from typing import Any


def convert_old_to_new(old_config: dict) -> dict:
    new_config: dict[str, Any] = {
        "name": old_config["name"],
        "prefixes": old_config["prefixes"],
        "database_file": old_config["database"],
        "data_path": old_config["data"],
        "webhook": old_config["webhook"],
        "use_extras": old_config["use_extras"]
    }

    if "donation" in old_config and old_config["donation"]:
        new_config["donation"] = old_config["donation"]
    else:
        new_config["donation"] = None

    fluxer_config = {
        "token": old_config["token"],
        "guild_invite": old_config["hq_server_invite"],
        "guild_id": old_config["hq_server_id"],
        "bot_invite": old_config["bot_invite_link"],
        "client_id": old_config["client_id"],
        "api_url": old_config["api"]
    }
    new_config["fluxer"] = fluxer_config

    if "discord" in old_config and old_config["discord"]:
        discord_old = old_config["discord"]
        discord_config = {
            "token": discord_old["token"],
            "guild_invite": discord_old["server_invite"],
            "guild_id": discord_old["server_id"],
            "bot_invite": discord_old["bot_invite"],
            "client_id": 0,
            "api_url": "https://discord.com/api"
        }
        new_config["discord"] = discord_config
    else:
        new_config["discord"] = None

    if "api_server" in old_config and old_config["api_server"]:
        api_server_old = old_config["api_server"]

        fluxer_api_config = {
            "client_id": api_server_old["client_id"],
            "client_secret": api_server_old["client_secret"]
        }

        discord_api_config = {"client_id": 0, "client_secret": ""}

        api_server_config = {
            "enabled": api_server_old["enabled"],
            "domain": api_server_old["domain"],
            "port": api_server_old["port"],
            "database": api_server_old["database"],
            "fluxer": fluxer_api_config,
            "discord": discord_api_config
        }
        new_config["api_server"] = api_server_config
    else:
        new_config["api_server"] = None

    if "website" in old_config and old_config["website"]:
        website_old = old_config["website"]
        website_config = {
            "dashboard": website_old["dashboard"],
            "home": website_old["home"],
            "terms": website_old["terms"],
            "privacy": website_old["privacy"],
            "contact": website_old["contact"]
        }
        new_config["website"] = website_config
    else:
        new_config["website"] = None

    return new_config


old_config_path = input("Enter old config path: ")
new_config_path = input("Enter new config path: ")

with open(old_config_path) as f:
    old_config = json.loads(f.read())

new_config = convert_old_to_new(old_config)

with open(new_config_path, "w+") as f:
    f.write(json.dumps(new_config, indent=4))

print("Config migrated.")
