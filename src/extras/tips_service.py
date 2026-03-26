import threading
import random
import asyncio

import fluxer
from fluxer import gateway

from .down_runner import report_bot
from ..backend.config import Config
from ..backend.data_reader import DataReader
from ..backend.template_utils import Template


async def tip_loop(bot: fluxer.Bot, get_ready):
    tips = DataReader.instance["tips.json"]
    refresh_timer = 5 * 60

    current_bucket = tips[:]
    random.shuffle(current_bucket)
    while True:
        if get_ready():
            tip = current_bucket.pop(0)
            config = Config.instance
            parsed = Template.from_string(tip).compute({
                "prefix": config.prefixes[0],
                "config": config.__dict__
            }, "")

            await bot._gateway._send(gateway.GatewayPayload(
                op = gateway.GatewayOpcode.PRESENCE_UPDATE,
                d = {
                    "status": "online",
                    "custom_status": {
                        "text": parsed,
                        "emoji_name": "",
                        "emoji_id": ""
                    },
                    "since": None,
                    "afk": False
                }
            ))

            # await report_bot("tip", parsed)
            await asyncio.sleep(refresh_timer)
        else:
            await asyncio.sleep(10)

        if len(current_bucket) == 0:
            current_bucket = tips[:]
            random.shuffle(current_bucket)

