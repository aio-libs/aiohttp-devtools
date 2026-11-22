import asyncio
import os
import signal
import sys
from collections.abc import Callable
from pathlib import Path
from types import FrameType
from typing import NoReturn

import pytest
from aiohttp import ClientSession, ClientTimeout

from aiohttp_devtools.runserver.config import Config
from aiohttp_devtools.runserver.serve import _interrupt_once, _run_until_interrupted
from aiohttp_devtools.runserver.watch import AppTask

from .conftest import FileTree


@pytest.mark.skipif(sys.platform == "win32", reason="Tested manually on Windows, see cleanup_app.py")
async def test_server_cleanup_by_url() -> None:
    async def is_server_running() -> bool:
        async with ClientSession(timeout=ClientTimeout(total=1)) as session:
            for i in range(30):
                try:
                    async with session.get("http://localhost:8000/") as r:
                        assert r.status == 200
                        text = await r.text()
                        assert "hello, world" in text
                        return True
                except OSError:  # pragma: no cover
                    await asyncio.sleep(0.5)
        return False  # pragma: no cover

    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-c", "from aiohttp_devtools.cli import runserver; runserver()",  # same as `adev runserver`
        Path(__file__).parent / "cleanup_app.py", "--shutdown-by-url", "-v",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        assert await is_server_running()
    finally:
        proc.terminate()

    await asyncio.sleep(2)
    stdout, stderr = await proc.communicate()
    assert b"process stopped via shutdown endpoint" in stderr
    lines = tuple(x[6:] for x in stdout.decode('UTF-8').splitlines() if x.startswith('====> '))
    assert lines == ("CTX BEFORE", "STARTUP", "SHUTDOWN", "CTX AFTER")


@pytest.mark.skipif(sys.platform == "win32", reason="SIGINT can't be sent to a process on Windows")
@pytest.mark.parametrize("stage", ("cleanup", "close"))
async def test_second_sigint_does_not_interrupt_shutdown(
    stage: str, tmpworkdir: Path, mktree: Callable[[FileTree], None], unused_tcp_port: int
) -> None:
    mktree({
        "stage": stage,
        "app.py": """\
import asyncio
from pathlib import Path

from aiohttp import web

tasks = set()


async def hello(request):
    return web.Response()


async def pause(stage):
    # The test holds up one stage of the shutdown, until it has sent the second SIGINT.
    if Path("stage").read_text() == stage:
        Path("paused").touch()
        for _ in range(500):
            resume = Path("resume").exists()
            # Sleep after the last check as well: if that SIGINT cancels this task, it's raised here.
            await asyncio.sleep(0.01)
            if resume:
                break


async def background():
    try:
        await asyncio.Event().wait()
    finally:
        # This task outlives the cleanup of the app, so it's cancelled when the event loop is closed.
        await pause("close")


async def context(app):
    tasks.add(asyncio.create_task(background()))
    yield
    await pause("cleanup")
    Path("cleaned").touch()


app = web.Application()
app.router.add_get("/", hello)
app.cleanup_ctx.append(context)
"""
    })
    app_task = AppTask(Config(app_path="app.py", root_path=str(tmpworkdir), main_port=unused_tcp_port))
    app_task._start_dev_server()
    process = app_task._process
    try:
        assert process.pid is not None
        async with ClientSession(timeout=ClientTimeout(total=1)) as session:
            for i in range(50):  # pragma: no branch
                try:
                    async with session.get(f"http://localhost:{unused_tcp_port}/"):
                        break
                except OSError:
                    await asyncio.sleep(0.1)
            # Wait for the app to be idle again: a signal which arrives just before its event loop
            # starts to wait for events is only handled when the next event wakes the loop up.
            await asyncio.sleep(0.25)
            # Ctrl+C in a terminal is sent to the app process as well as to adev.
            os.kill(process.pid, signal.SIGINT)
            async with asyncio.timeout(10):
                while not (tmpworkdir / "paused").exists():
                    await asyncio.sleep(0.01)
            # adev then stops the app process with SIGINT, while it's already shutting down.
            os.kill(process.pid, signal.SIGINT)
            (tmpworkdir / "resume").touch()
            process.join(5)
        # If the second SIGINT gets through, it either cancels the cleanup of the app (without
        # any error) or it's raised as KeyboardInterrupt while the event loop is being closed.
        assert (tmpworkdir / "cleaned").exists()
        assert process.exitcode == 0
    finally:
        process.kill()
        process.join()


@pytest.mark.skipif(sys.platform == "win32", reason="SIGINT can't be sent to a process on Windows")
async def test_sigint_during_request_does_not_skip_cleanup(
    tmpworkdir: Path, mktree: Callable[[FileTree], None], unused_tcp_port: int
) -> None:
    mktree({
        "app.py": """\
import asyncio
import time
from pathlib import Path

from aiohttp import web


async def hello(request):
    return web.Response()


async def busy(request):
    # With Python 3.12+, aiohttp starts a handler in the task of its connection. Once it has
    # awaited something, it's run by a task of its own, which the task of the connection awaits.
    await asyncio.sleep(0)
    Path("busy").touch()
    # The test sends SIGINT while this is executing.
    for _ in range(500):
        if Path("resume").exists():
            break
        time.sleep(0.01)
    return web.Response()


async def context(app):
    yield
    Path("cleaned").touch()


app = web.Application()
app.router.add_get("/", hello)
app.router.add_get("/busy", busy)
app.cleanup_ctx.append(context)
"""
    })
    app_task = AppTask(Config(app_path="app.py", root_path=str(tmpworkdir), main_port=unused_tcp_port))
    app_task._start_dev_server()
    process = app_task._process
    try:
        assert process.pid is not None
        async with ClientSession() as session:
            for i in range(50):  # pragma: no branch
                try:
                    async with session.get(f"http://localhost:{unused_tcp_port}/"):
                        break
                except OSError:
                    await asyncio.sleep(0.1)
            request = asyncio.create_task(session.get(f"http://localhost:{unused_tcp_port}/busy"))
            async with asyncio.timeout(10):
                while not (tmpworkdir / "busy").exists():
                    await asyncio.sleep(0.01)
            # adev stops the app process with SIGINT, e.g. to restart it.
            os.kill(process.pid, signal.SIGINT)
            (tmpworkdir / "resume").touch()
            process.join(5)
            # If the handler is interrupted by KeyboardInterrupt, the task which awaits it raises
            # that again later, which ends the cleanup of the app as soon as it has started.
            assert (tmpworkdir / "cleaned").exists()
            assert process.exitcode == 0
            assert (await request).status == 200
    finally:
        process.kill()
        process.join()


def test_run_until_interrupted() -> None:
    handler = signal.signal(signal.SIGINT, signal.default_int_handler)
    try:
        with asyncio.Runner() as runner:
            loop = runner.get_loop()
            loop.call_soon(signal.raise_signal, signal.SIGINT)
            loop.call_later(10, loop.stop)  # Fail, rather than wait forever.
            _run_until_interrupted(loop)
        assert signal.getsignal(signal.SIGINT) == signal.SIG_IGN
    finally:
        signal.signal(signal.SIGINT, handler)


def test_run_until_interrupted_app_handler() -> None:
    def app_handler(signum: int, frame: FrameType | None) -> NoReturn:
        raise KeyboardInterrupt

    # A handler which the app has set itself is left in place.
    handler = signal.signal(signal.SIGINT, app_handler)
    try:
        with asyncio.Runner() as runner:
            loop = runner.get_loop()
            loop.call_soon(signal.raise_signal, signal.SIGINT)
            loop.call_later(10, loop.stop)  # Fail, rather than wait forever.
            with pytest.raises(KeyboardInterrupt):
                _run_until_interrupted(loop)
        assert signal.getsignal(signal.SIGINT) is app_handler
    finally:
        signal.signal(signal.SIGINT, handler)


def test_interrupt_once_loop_closed() -> None:
    handler = signal.getsignal(signal.SIGINT)
    # With --shutdown-by-url, SIGINT may arrive when the app has been stopped already.
    loop = asyncio.new_event_loop()
    loop.close()
    try:
        _interrupt_once(loop, asyncio.Event(), signal.SIGINT, None)
        assert signal.getsignal(signal.SIGINT) == signal.SIG_IGN
    finally:
        signal.signal(signal.SIGINT, handler)
