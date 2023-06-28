"""
Test script for checking if cleanup/shutdown handlers are called.
Used in test_runserver_cleanup.py.

This test has proved to be quite difficult to automate in Windows
(see discussion at https://github.com/aio-libs/aiohttp-devtools/pull/549)
so it must be done manually as per the protocol below.

Test Protocol:

1. Run a Windows console such as Git Bash; ensure a working Python version is available
2. ``cd`` to the main aiohttp-devtools directory (root of the git repo)
3. Run ``python -c "from aiohttp_devtools.cli import runserver; runserver()" -v tests/cleanup_app.py``
4. The console output should show the "CTX BEFORE" and "STARTUP" output from the code below
5. Edit this file, e.g. a simple whitespace change, and save
6. The console output should show the "SHUTDOWN" and "CTX AFTER" output, followed by the startup output
7. End the process in the console with Ctrl-C
8. The console should again show the shutdown output
"""
from aiohttp import web


async def hello(_request):
    return web.Response(text="hello, world")


async def startup(_app):
    print("====> STARTUP")


async def context(_app):
    print("====> CTX BEFORE")
    yield
    print("====> CTX AFTER")


async def shutdown(_app):
    print("====> SHUTDOWN")


app = web.Application()
app.router.add_get("/", hello)
app.on_startup.append(startup)
app.cleanup_ctx.append(context)
app.on_shutdown.append(shutdown)
