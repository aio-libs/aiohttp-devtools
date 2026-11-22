"""
App for checking that the startup and cleanup/shutdown handlers are called.
Used in test_runserver_cleanup.py.
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
