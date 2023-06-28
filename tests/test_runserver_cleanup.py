import sys
import asyncio
from pathlib import Path
from aiohttp import ClientSession, ClientTimeout
from .conftest import forked
import logging  # pytest --log-cli-level=INFO


@forked  # forked doesn't run on Windows and is skipped - see cleanup_app.py instead
async def test_server_cleanup_byurl():

    async def check_server_running():
        async with ClientSession(timeout=ClientTimeout(total=1)) as session:
            for i in range(30):
                try:
                    async with session.get("http://localhost:8000/") as r:
                        assert r.status == 200
                        text = await r.text()
                        assert "hello, world" in text
                        return
                except OSError:
                    await asyncio.sleep(0.5)
                except asyncio.TimeoutError:
                    pass
        raise RuntimeError("Failed to reach the server")

    logging.info("runserver")
    proc = await asyncio.create_subprocess_exec(
        sys.executable, '-c', 'from aiohttp_devtools.cli import runserver; runserver()',  # same as `adev runserver`
        str(Path(__file__).parent/'cleanup_app.py'), '--shutdown-by-url', '-v',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    ok = False
    try:
        logging.info("check_server_running")
        await asyncio.create_task(check_server_running())
        logging.info("success")
        await asyncio.sleep(2)
        ok = True
    finally:
        logging.info("terminating")
        proc.terminate()
    if ok:
        stdout, stderr = await proc.communicate()
        logging.info(repr((stdout, stderr, proc.returncode)))
        assert b'process stopped via shutdown endpoint' in stderr
        lines = [x[6:] for x in stdout.decode('UTF-8').splitlines() if x.startswith('====> ')]
        logging.info(repr(lines))
        assert lines == ["CTX BEFORE", "STARTUP", "SHUTDOWN", "CTX AFTER"]
    else:
        assert False
