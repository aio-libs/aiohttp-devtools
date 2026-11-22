import asyncio
import os
import signal
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from aiohttp import ClientSession, ClientTimeout

from aiohttp_devtools.runserver.config import Config
from aiohttp_devtools.runserver.serve import _interrupt_once
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
            # Wait for the app to be idle again: a KeyboardInterrupt which is raised while its event loop
            # is still busy with the request can leave the app unable to shut down (seen with PyPy).
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


def test_interrupt_once() -> None:
    handler = signal.getsignal(signal.SIGINT)
    try:
        with pytest.raises(KeyboardInterrupt):
            _interrupt_once(signal.SIGINT, None)
        assert signal.getsignal(signal.SIGINT) == signal.SIG_IGN
    finally:
        signal.signal(signal.SIGINT, handler)
