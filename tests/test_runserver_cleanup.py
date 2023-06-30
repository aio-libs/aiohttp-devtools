import asyncio
import sys
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout

from .conftest import forked


@forked  # forked doesn't run on Windows and is skipped - see cleanup_app.py instead
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
                except OSError:
                    await asyncio.sleep(0.5)
                except asyncio.TimeoutError:
                    pass
        return False

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
