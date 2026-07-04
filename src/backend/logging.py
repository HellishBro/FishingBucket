import datetime
import logging
import traceback
from pathlib import Path
from typing import Callable, Any

from .config import Config

def get_log_file(postfix: str = "") -> Path:
    return Config.instance.log_directory / f"{Config.init_time.strftime(Config.instance.log_time_format)}{postfix}.log"

def start_log(name: str, postfix: str = "") -> tuple[Callable[..., None], Callable[[BaseException], None]]:
    logger = logging.getLogger(name + postfix)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(get_log_file(postfix))
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)

    prefix = f"{datetime.datetime.now() - Config.init_time} [{name}{postfix}] "

    def info(*data: Any):
        msg = prefix + ' '.join(str(d) for d in data)
        print(msg)
        logger.info(msg)

    def err(e: BaseException):
        msg = prefix + "".join(traceback.format_exception(type(e), e, e.__traceback__))
        print(msg)
        logger.error(msg)

    return info, err
