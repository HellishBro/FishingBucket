import traceback
import aiohttp
from fluxer.http import _get_user_agent

from ..backend.config import Config

async def report_bot(status: str, reason: str = ""):
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://web.fluxer.app/api/v1/oauth2/applications/{Config.instance.bot_client_id}/bot"
            new_bio = Config.instance.bot_bios[status].replace("{}", reason)
            async with session.patch(url, json={
                "bio": new_bio
            }, headers={
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Authorization": Config.instance.user_token,
                "Content-Type": "application/json",
                "Origin": "https://web.fluxer.app",
                "Referer": "https://web.fluxer.app",
                "Host": "web.fluxer.app",
                "User-Agent": _get_user_agent()
            }) as res:
                if res.status != 200:
                    print(f"Reported bot status: {status!r} with reason={reason!r}")
                    print(f"Response: {res.status}")
                    print(f"{await res.text()}")
    except BaseException as e:
        print("".join(traceback.format_exception(type(e), e, e.__traceback__)))
