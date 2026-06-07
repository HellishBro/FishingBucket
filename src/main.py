import asyncio
import signal
import traceback
import time
import os

from .backend.config import Config
from .backend.data_reader import DataReader
from .backend.database import Database
from .interaction import Interactions
from .backend.cache import CacheStatus
from . import commands
from .api_server import app as api_app, ApplicationContext
from .startup import setup_events, setup_commands
from .service.server import setup_instances


def run(config_file: str):
    Config(config_file)
    Database(Config.instance.database_file)
    DataReader(Config.instance.data_path)
    CacheStatus()

    setup_commands.setup()
    commands.setup_commands()

    servers = setup_instances()
    Interactions()

    do_run = True

    async def run_once():
        starts = [asyncio.Future()] + [server.start() for server in servers]
        ends = [Database.instance.close()] + [server.close() for server in servers]
        if Config.instance.api_server.enabled:
            starts.append(api_app.serve())
            ends.append(api_app.close())

        try:
            await asyncio.gather(*starts)
        finally:
            await asyncio.gather(*ends)
            print("Finished ending everything")

    def shutdown(reason: str, frame = None):
        nonlocal do_run
        if frame:
            import traceback
            traceback.print_stack(frame)

        print("Shutting down:", reason)
        do_run = False
        raise Exception()

    signal.signal(signal.SIGTERM, lambda s, f: shutdown(f"SIGTERM reached {s}; {f}", f))

    attempts = 0
    while do_run:
        print("Trying to connect...")
        start_time = time.time()
        err = None
        try:
            try:
                asyncio.run(Database.instance.init())

                for server in servers:
                    setup_events.setup(server)

                api_app.set_context(ApplicationContext(Database.instance, Config.instance))
                asyncio.run(run_once())
            except (SystemExit, KeyboardInterrupt) as e:
                shutdown(repr(e))
            except Exception as e:
                print("".join(traceback.format_exception(type(e), e, e.__traceback__)))
                err = e
            except BaseException as be:
                print("".join(traceback.format_exception(type(be), be, be.__traceback__)))
                err = be
        except Exception: pass

        print("Trying to restart")
        if not do_run:
            break

        readied = any(server.ready for server in servers)
        if not readied:
            attempts += 1
        else:
            attempts = 0

        session_time = time.time() - start_time
        wait_sec = 10 + 10 * min(attempts, 30)
        print(f"Resetting... error: {err}. Session time: {session_time:.2f}s, readied? {readied}. Connection attempt {attempts}. Waiting for {wait_sec} seconds.")

        for server in servers:
            server.clear_events()

        error_guess = err.__class__.__name__
        print(f"Error: {error_guess}.")

        time.sleep(wait_sec)
        print("Retrying connect...")

    print("Shutting down")
    os._exit(1)
