import ast
import asyncio
import traceback
import fluxer
from asyncio import run as async_run, sleep, iscoroutine
import time

from .backend.config import Config
from .backend.data_reader import DataReader
from .backend.database import Database
from .interaction import Interactions
from .backend.cache import CacheStatus
from . import commands, interactions_impl
from .commands import command_impl

def run(config_file: str):
    Config(config_file)
    Database(Config.instance.database_file)
    DataReader(Config.instance.data_path)
    CacheStatus()

    app = fluxer.Bot(command_prefix=Config.instance.prefixes[0], intents=fluxer.Intents.default(), api_url=Config.instance.api_url)
    Interactions()
    builtin_print = print

    @app.command(name="eval")
    async def eval_(message: fluxer.Message):
        code, = await commands.parse_command(message, [str], app, "eval")
        if int(message.author.id) in Config.instance.devs:
            try:
                comp = compile(code, "<string>", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)

                _output = []
                def print(*args):
                    builtin_print(*args)
                    _output.append(" ".join(str(arg) for arg in args))

                res = eval(comp, globals(), locals())
                if iscoroutine(res):
                    await res

                returned = "\n".join(_output)
            except Exception as e:
                returned = "".join(traceback.format_exception(type(e), e, e.__traceback__))

            m = await message.reply("", embeds=[fluxer.Embed(
                "Code eval",
                f"**Input**\n```py\n{code}\n```\n\n**Output**\n```\n{returned[:min(len(returned), 1000)]}\n```"
            ).to_dict()])

            await sleep(30)
            await message.delete()
            await m.delete()

    if Config.instance.use_extras:
        from .extras.down_runner import report_bot
        from .extras.tips_service import run_tip_loop
    else:
        from .extras.nothing import no_op_coro as report_bot
        from .extras.nothing import no_op_func as run_tip_loop

    run_tip_loop(app, lambda: interactions_impl.ready)
    attempts = 0
    while True:
        print("Trying to connect...")
        start_time = time.time()
        err = None
        try:
            async_run(Database.instance.init())
            command_impl.setup(app)
            interactions_impl.setup(app)
            app.run(Config.instance.token)
        except KeyboardInterrupt:
            quit()
        except Exception as e:
            print("".join(traceback.format_exception(type(e), e, e.__traceback__)))
            err = e
        except BaseException as be:
            print("".join(traceback.format_exception(type(be), be, be.__traceback__)))
            err = be

        if not interactions_impl.ready:
            attempts += 1
        else:
            attempts = 0

        session_time = time.time() - start_time
        wait_sec = 10 + 10 * min(attempts, 30)
        print(f"Resetting... error: {err}. Session time: {session_time:.2f}s, readied? {interactions_impl.ready}. Connection attempt {attempts}. Waiting for {wait_sec} seconds.")
        async_run(Database.instance.close())
        commands.clear()
        interactions_impl.clear(app)

        error_guess = err.__class__.__name__
        status = "down."
        if isinstance(err, fluxer.errors.Forbidden):
            error_guess = "API DISABLED"
            status = f"Fluxer API is disabled. Retrying connection in {wait_sec} seconds."
        elif isinstance(err, asyncio.TimeoutError):
            error_guess = "CONNECTION TIMEOUT"
            status = f"Fluxer API timeout. Retrying connection in {wait_sec} seconds."
        elif isinstance(err, RuntimeError):
            error_guess = "CONNECTION TIMEOUT"
            status = f"Fluxer API timeout. Retrying connection in {wait_sec} seconds."

        print(f"Error guess: {error_guess}, status: {status}")
        async_run(report_bot("down", status))

        time.sleep(wait_sec)
        print("Retrying connect...")
