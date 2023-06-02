import asyncio
from aiohttp import ClientSession, ClientTimeout
from pytest_toolbox import mktree
import pytest
from aiohttp_devtools.runserver import runserver
from .conftest import forked
from tempfile import NamedTemporaryFile
import sys
from pathlib import Path


_test_app = """\
from aiohttp import web
import logging

async def hello(request):
    return web.Response(text='hello, world')

app = web.Application()
app.router.add_get('/', hello)

async def startup(_app):
    with open(<<filename>>,'a') as fh:
        print("STARTUP", file=fh)
app.on_startup.append(startup)

async def context(_app):
    with open(<<filename>>,'a') as fh:
        print("CTX BEFORE", file=fh)
    yield
    with open(<<filename>>,'a') as fh:
        print("CTX AFTER", file=fh)
app.cleanup_ctx.append(context)

async def shutdown(_app):
    with open(<<filename>>,'a') as fh:
        print("SHUTDOWN", file=fh)
app.on_shutdown.append(shutdown)
"""


# TODO: Can't find a way to fix these warnings, maybe fixed in aiohttp 4.
@pytest.mark.filterwarnings(r"ignore:unclosed:ResourceWarning")
@forked  # forked doesn't run on Windows and is skipped
def test_server_cleanup(tmpworkdir, smart_caplog):
    tempf = NamedTemporaryFile(dir=tmpworkdir, delete=False)
    tempf.close()
    mktree(
        tmpworkdir,
        {"app.py": _test_app.replace("<<filename>>", repr(tempf.name))},
    )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    args = runserver(app_path="app.py")
    aux_app = args["app"]
    for startup in aux_app.on_startup:
        loop.run_until_complete(startup(aux_app))

    async def check_server_running():
        async with ClientSession(timeout=ClientTimeout(total=1)) as session:
            for i in range(50):
                try:
                    async with session.get("http://localhost:8000/") as r:
                        assert r.status == 200
                        text = await r.text()
                        assert "hello, world" in text
                        return
                except OSError:
                    await asyncio.sleep(0.1)
        raise RuntimeError("Failed to reach the server")

    try:
        loop.run_until_complete(check_server_running())
    finally:
        for shutdown in aux_app.on_shutdown:
            loop.run_until_complete(shutdown(aux_app))
        loop.run_until_complete(aux_app.cleanup())
    assert (
        "adev.server.dft INFO: Starting aux server at http://localhost:8001 ◆\n"
        "adev.server.dft INFO: Starting dev server at http://localhost:8000 ●\n"
    ) in smart_caplog

    with open(tempf.name) as fh:
        assert list(fh) == ["CTX BEFORE\n", "STARTUP\n", "SHUTDOWN\n", "CTX AFTER\n"]

    loop.run_until_complete(asyncio.sleep(0.25))  # TODO(aiohttp 4): Remove this hack


if sys.platform.startswith("win32"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


@pytest.mark.skipif(
    not sys.platform.startswith("win32"),
    reason="Config.shutdown_by_url only defaults to True on Windows",
)
@pytest.mark.xfail(reason="Work on this test is still in progress")
async def test_server_cleanup_byurl(tmpworkdir):
    tempf = NamedTemporaryFile(dir=tmpworkdir, delete=False)
    tempf.close()
    mktree(
        tmpworkdir,
        {
            "app.py": _test_app.replace("<<filename>>", repr(tempf.name)),
            "runserv.py": """\
import sys
sys.path.append(<<sys_path>>)
from aiohttp.web import run_app
from aiohttp_devtools.runserver.main import runserver
run_app( **runserver( app_path=<<app_py>>, main_port=8123 ))""".replace(
                "<<app_py>>", repr(str(Path(tmpworkdir, "app.py")))
            ).replace(
                "<<sys_path>>", repr(str(Path(__file__).parent.parent))
            ),
        },
    )

    async def check_server_running():
        async with ClientSession(timeout=ClientTimeout(total=1)) as session:
            for i in range(5):
                try:
                    async with session.get("http://localhost:8123/") as r:
                        assert r.status == 200
                        text = await r.text()
                        assert "hello, world" in text
                        return
                except OSError:
                    await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    pass
        raise RuntimeError("Failed to reach the server")

    # TODO: currently we're failing at `set_start_method('spawn')` in aiohttp_devtools.runserver.main.runserver()
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(Path(tmpworkdir, "runserv.py")),
        # stdout=asyncio.subprocess.PIPE,
        # stderr=asyncio.subprocess.PIPE,
        cwd=tmpworkdir,
    )

    # stdout, stderr = await proc.communicate()
    # print(repr((stdout, stderr, proc.returncode)))
    await asyncio.create_task(check_server_running())
    proc.terminate()

    # assert (
    #    "adev.server.dft INFO: Starting aux server at http://localhost:8001 ◆\n"
    #    "adev.server.dft INFO: Starting dev server at http://localhost:8000 ●\n"
    # ) in smart_caplog

    with open(tempf.name) as fh:
        assert list(fh) == ["CTX BEFORE\n", "STARTUP\n", "SHUTDOWN\n", "CTX AFTER\n"]
