import json

import pydantic
from aiohttp import ClientSession

from .generic import hook_command
from .specific import get_uid
from ..backend.database import Database
from ..backend.import_system import NativeImporter, TupperboxImporter, PluralKitImporter, UtterImporter
from ..backend.models import ProxyGroup, Proxy
from ..import_helper import import_native, import_tupperbox, import_pluralkit, import_utter, export_native
from ..service import Context, Embed, File


def setup():
    @hook_command("import")
    async def _(context: Context, file: str | None, origin: str | None):
        if not context.message.attachments and not file:
            await context.reply("Error: no import file found.")
            return

        if file:
            filename = file.split("?")[0].split("/")[-1]
            async with ClientSession() as session:
                async with session.get(file) as response:
                    contents = await response.read()
        else:
            filename = context.message.attachments[0].filename
            contents = await context.message.attachments[0].read()

        origin = origin or (
            "fishing_bucket" if "proxies" in filename and filename.endswith(".json") else
            "tupperbox" if "tupper" in filename and filename.endswith(".json") else
            "pluralkit" if "system" in filename and filename.endswith(".json") else
            "utter" if "utter" in filename and filename.endswith(".json") else
            None
        )

        if origin is None:
            await context.reply(f"Error: cannot guess import file origin with the filename {filename!r}.")
            return

        origin_names = {
            "fishing_bucket": "Fishing Bucket",
            "tupperbox": "Tupperbox",
            "pluralkit": "PluralKit",
            "utter": "Utter"
        }

        confirmation = await context.reply(f"Importing from {origin_names[origin]}")
        try:
            await context.message.delete()
        except: pass

        owner = await get_uid(context, True)

        if origin == "fishing_bucket":
            cls = NativeImporter()
        elif origin == "tupperbox":
            cls = TupperboxImporter()
        elif origin == "pluralkit":
            cls = PluralKitImporter()
        elif origin == "utter":
            cls = UtterImporter()
        else:
            raise Exception("unreachable")

        try:
            cls.import_data(contents, owner)
        except (json.JSONDecodeError, pydantic.ValidationError) as e:
            await confirmation.reply(f"Error: cannot parse file")
            return

        user_proxies = await Database.instance.get_user_proxies(owner)
        user_groups = await Database.instance.get_user_groups(owner)

        updated_proxies = 0
        updated_groups = 0

        inserted_proxy_instances: list[Proxy] = []
        inserted_group_instances: list[ProxyGroup] = []

        groups_queue: list[ProxyGroup] = []
        for group in cls.groups:
            founds = [g for g in user_groups if g.name == group.name]
            if founds:
                in_database = founds[0]
                await Database.instance.update_group_tag(in_database.id, group.tag)
                await Database.instance.update_group_description(in_database.id, group.description)
                updated_groups += 1
            else:
                groups_queue.append(group)

        while groups_queue:
            to_remove: list[int] = []
            for idx, group in enumerate(groups_queue):
                if group.parent not in groups_queue:
                    inserted_group_instances.append(await Database.instance.put_group(group))
                    to_remove.append(idx)
            for idx in sorted(to_remove, reverse=True):
                groups_queue.pop(idx)

        for proxy in cls.proxies:
            founds = [p for p in user_proxies if p.name == proxy.name]
            if founds:
                in_database = founds[0]
                await Database.instance.update_description(in_database.id, proxy.description)
                await Database.instance.update_nickname(in_database.id, proxy.nickname)
                await Database.instance.update_avatar(in_database.id, proxy.avatar_url)
                await Database.instance.update_trigger(in_database.id, proxy.triggers)
                updated_proxies += 1
            else:
                inserted_proxy_instances.append(await Database.instance.put_proxy(proxy))

        inserted_proxies = len(cls.proxies) - updated_proxies
        inserted_groups = len(cls.groups) - updated_groups

        await confirmation.message.edit(
            f"Proxies loaded! Updated {updated_proxies} proxies and {updated_groups} groups, and inserted {inserted_proxies} new proxies and {inserted_groups} new groups!")

        proxies_text = "\n".join(
            f"- **{p.name}** (`{p.id}`)" for p in inserted_proxy_instances[:min(len(inserted_proxy_instances), 20)]
        ) or "- No proxies were added!"

        if len(inserted_proxy_instances) > 20:
            proxies_text += f"\n...... and {len(inserted_proxy_instances) - 20} more"

        groups_text = "\n".join(
            f"- **{g.name}** (`{g.id}`)" for g in inserted_group_instances[:min(len(inserted_group_instances), 20)]
        ) or "- No groups were added!"

        if len(inserted_group_instances) > 20:
            groups_text += f"\n...... and {len(inserted_group_instances) - 20} more"

        await confirmation.reply("", embeds=[
            Embed(
                f"{context.author.display_name}'s New Imports",
                f"New proxies:\n{proxies_text}\n\nNew groups:\n{groups_text}"
            )
        ])


    @hook_command("export")
    async def _(context: Context):
        owner = await get_uid(context)
        groups = await Database.instance.get_user_groups(owner)
        proxies = await Database.instance.get_user_proxies(owner)
        jsoned = json.dumps(export_native(groups, proxies), indent=4)
        file = File(
            "proxies.json",
            "",
            jsoned.encode("utf-8")
        )
        if not (await context.get_channel(context.message.channel_id)).dm:
            dm = await context.author.get_dm()
            await dm.send("Proxies exported!", files=[file])
            await context.reply("I've sent your exported proxies into your DM!")
        else:
            await context.reply("Proxies exported!", files=[file])
