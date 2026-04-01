import base64
import gzip
import json
import traceback
from io import BytesIO

import fluxer

from .. import response
from ..backend.database import Database
from ..commands import register_command, register_group
from ..import_helper import import_tupperbox, import_native, import_pluralkit, export_native
from ..backend.models import optional_type
from ..backend.utils import read_file

def setup(bot: fluxer.Bot):
    register_group("io", "Import/Export Commands", "Save or load your proxies.")

    @register_command([optional_type(str)], bot, "import", """
    Imports exported proxy data.
    This can be used to import from exports done by this bot or other similar programs.
    The export file can be attached as an attachment or send as a link.

    List of supported import targets:
    - Fishing Bucket
    - Tupperbox
    - Pluralkit
    """, "import [file url]", ["import", "import https://example.com/proxies.json.gz.a85"], "io")
    async def import_(message: fluxer.Message, url: str | None):
        if not message.attachments and not url:
            await response.respond(message, "Error! No import file found!")
            return

        if message.attachments:
            first_attachment = message.attachments[0]
            title = first_attachment.filename
            contents = await read_file(first_attachment.url)
        else:
            title = url.split("?")[0].split("/")[-1]
            contents = await read_file(url)

        imported_groups = []
        imported_proxies = []
        if "tuppers" in title and title.endswith(".json"):
            m = await response.respond(message, "Loading from Tupperbox!")
            try:
                res = json.loads(contents)
                groups, proxies = import_tupperbox(res, int(message.author.id))
                for g in groups:
                    await Database.instance.put_group(g)
                    imported_groups.append(g)
                for p in proxies:
                    await Database.instance.put_proxy(p)
                    imported_proxies.append(p)

                await m.edit(
                    f"Proxies loaded! Imported {len(imported_proxies)} proxies and {len(imported_groups)} groups!")
                await message.delete()
            except fluxer.FluxerException:
                pass
            except Exception as e:
                print(f"{e} when loading from Tupperbox: {contents}")
                await m.reply("Error! Cannot load from Tupperbox! Is the uploaded file corrupted?")
                await message.delete()
                return

        elif "proxies" in title and title.endswith(".a85"):
            m = await response.respond(message, "Loading from Fishing Bucket!")
            try:
                res = json.loads(gzip.decompress(base64.a85decode(contents.encode("utf-8"))).decode("utf-8"))
                groups, proxies = import_native(res, int(message.author.id))
                for g in groups:
                    await Database.instance.put_group(g)
                    imported_groups.append(g)
                for p in proxies:
                    await Database.instance.put_proxy(p)
                    imported_proxies.append(p)

                await m.edit(
                    f"Proxies loaded! Imported {len(imported_proxies)} proxies and {len(imported_groups)} groups!")
                await message.delete()
            except fluxer.FluxerException:
                pass
            except Exception as e:
                print(f"{e} when loading from Fishing Bucket: {contents}")
                await m.reply(f"Error! Cannot load from Fishing Bucket! Is the uploaded file corrupted?")
                await message.delete()
                return


        elif "system" in title and title.endswith(".json"):
            m = await response.respond(message, "Loading from Pluralkit!")
            try:
                res = json.loads(contents)
                groups, proxies = import_pluralkit(res, int(message.author.id))
                for g in groups:
                    await Database.instance.put_group(g)
                    imported_groups.append(g)
                for p in proxies:
                    await Database.instance.put_proxy(p)
                    imported_proxies.append(p)

                await m.edit(
                    f"Proxies loaded! Imported {len(imported_proxies)} proxies and {len(imported_groups)} groups!")
                await message.delete()
            except fluxer.FluxerException:
                pass
            except Exception as e:
                print("".join(traceback.format_exception(type(e), e, e.__traceback__)))
                # print(f"{e} when loading from Pluralkit: {contents}")
                await m.reply(f"Error! Cannot load from Pluralkit! Is the uploaded file corrupted?")
                await message.delete()
                return

        else:
            await response.respond(message,
                                   f"Error! Unrecognized format! Use `{bot.command_prefix}help import` to see a list of possible import targets!")
            await message.delete()
            return

        description = "\n".join(
            f"**{p.name}** (`{str(hex(p.id))[2:]}`)" for p in imported_proxies[:min(len(imported_proxies), 20)])
        if len(imported_proxies) > 20:
            description += f"\n...... and {len(imported_proxies) - 20} more"
        await m.reply("", embeds=[fluxer.Embed(f"{message.author.display_name}'s Imported Proxies",
                                               description or "No proxies were imported!").to_dict()])

    @register_command([optional_type(str)], bot, "reimport", """
    Reimports exported proxy data.
    Behaves similarly to `import`, except this command tries to update proxies if possible.
    Recommended if the `import` command was used before.
    Proxies and groups are checked by comparing their names.
    """, "reimport [file url]", ["reimport", "reimport https://example.com/proxies.json.gz.a85"], "io")
    async def reimport(message: fluxer.Message, url: str | None):
        if not message.attachments and not url:
            await response.respond(message, "Error! No import file found!")
            return

        if message.attachments:
            first_attachment = message.attachments[0]
            title = first_attachment.filename
            contents = await read_file(first_attachment.url)
        else:
            title = url.split("?")[0].split("/")[-1]
            contents = await read_file(url)

        if "tuppers" in title and title.endswith(".json"):
            m = await response.respond(message, "Loading from Tupperbox!")
            try:
                res = json.loads(contents)
                groups, proxies = import_tupperbox(res, int(message.author.id))
            except Exception as e:
                print(f"{e} when loading from Tupperbox: {contents}")
                await m.reply("Error! Cannot load from Tupperbox! Is the uploaded file corrupted?")
                await message.delete()
                return

        elif "proxies" in title and title.endswith(".a85"):
            m = await response.respond(message, "Loading from Fishing Bucket!")
            try:
                res = json.loads(gzip.decompress(base64.a85decode(contents.encode("utf-8"))).decode("utf-8"))
                groups, proxies = import_native(res, int(message.author.id))
            except Exception as e:
                print(f"{e} when loading from Fishing Bucket: {contents}")
                await m.reply(f"Error! Cannot load from Fishing Bucket! Is the uploaded file corrupted?")
                await message.delete()
                return

        elif "system" in title and title.endswith(".json"):
            m = await response.respond(message, "Loading from Pluralkit!")
            try:
                res = json.loads(contents)
                groups, proxies = import_pluralkit(res, int(message.author.id))
            except Exception as e:
                print("".join(traceback.format_exception(type(e), e, e.__traceback__)))
                # print(f"{e} when loading from Pluralkit: {contents}")
                await m.reply(f"Error! Cannot load from Pluralkit! Is the uploaded file corrupted?")
                await message.delete()
                return

        else:
            await response.respond(message,
                                   f"Error! Unrecognized format! Use `{bot.command_prefix}help import` to see a list of possible import targets!")
            await message.delete()
            return

        user_proxies = await Database.instance.get_user_proxies(message.author.id)
        user_groups = await Database.instance.get_user_groups(message.author.id)

        updated_proxies = 0
        updated_groups = 0

        inserted_proxy_instances = []

        for group in groups:
            founds = [g for g in user_groups if g.name == group.name]
            if founds:
                in_database = founds[0]
                await Database.instance.update_group_tag(in_database.id, group.tag)
                await Database.instance.update_group_description(in_database.id, group.description)
                updated_groups += 1
            else:
                await Database.instance.put_group(group)

        for proxy in proxies:
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

        inserted_proxies = len(proxies) - updated_proxies
        inserted_groups = len(groups) - updated_groups

        await m.edit(
            f"Proxies loaded! Updated {updated_proxies} proxies and {updated_groups} groups, and inserted {inserted_proxies} new proxies and {inserted_groups} new groups!")
        await message.delete()

        description = "\n".join(
            f"**{p.name}** (`{str(hex(p.id))[2:]}`)" for p in inserted_proxy_instances[:min(len(inserted_proxy_instances), 20)])
        if len(inserted_proxy_instances) > 20:
            description += f"\n...... and {len(inserted_proxy_instances) - 20} more"

        await m.reply("", embeds=[fluxer.Embed(f"{message.author.display_name}'s Newly Inserted Proxies",
                                               description or "No additional proxies were inserted!").to_dict()])

    @register_command([], bot, "export", """
    Generates an export of your proxies.
    This includes everything to import the proxy back into the bot.
    """, "export", ["export"], "io")
    async def export(message: fluxer.Message):
        groups = await Database.instance.get_user_groups(int(message.author.id))
        proxies = await Database.instance.get_user_proxies(int(message.author.id))
        jsoned = json.dumps(export_native(groups, proxies))
        contents = base64.a85encode(gzip.compress(jsoned.encode("utf-8"))).decode("utf-8")
        file = fluxer.File(
            BytesIO(contents.encode("utf-8")),
            filename="proxies.json.gz.a85"
        )
        if message.guild_id:
            await message.author.send("Proxies exported!", files=[file])
            await response.respond(message, "I've sent your exported proxies into your DM!")
        else:
            await message.reply("Proxies exported!", files=[file])
