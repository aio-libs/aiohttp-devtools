"""
Test script for checking if cleanup/shutdown handlers are called.
This test has proved to be quite difficult to automate in Windows
(see discussion at https://github.com/aio-libs/aiohttp-devtools/pull/549)
so it must be done manually as per the protocol below.
On Linux, it is handled via test_runserver_cleanup.py.

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
    return web.Response(text='hello, world')

app = web.Application()
app.router.add_get('/', hello)


async def startup(_app):
    print("====> STARTUP")
app.on_startup.append(startup)


async def context(_app):
    print("====> CTX BEFORE")
    yield
    print("====> CTX AFTER")
app.cleanup_ctx.append(context)


async def shutdown(_app):
    print("====> SHUTDOWN")
app.on_shutdown.append(shutdown)
