import asyncio

import aiohttp

from aiohttp_devtools.runserver import runserver
from aiohttp_devtools.runserver.serve import create_main_app
from aiohttp_devtools.runserver.watch import PyCodeEventHandler

from .conftest import mktree

SIMPLE_APP = {
    'app.py': """\
from aiohttp import web

async def hello(request):
    return web.Response(text='hello world')

def create_app(loop):
    app = web.Application(loop=loop)
    app.router.add_get('/', hello)
    return app"""}


async def test_start_runserver(loop, tmpworkdir):
    mktree(tmpworkdir, SIMPLE_APP)
    aux_app, observer, aux_port = runserver(app_path='app.py', loop=loop)
    assert isinstance(aux_app, aiohttp.web.Application)
    assert aux_port == 8001

    # this has started the app running in a separate process, check it's working. ugly but comprehensive check
    app_running = False
    async with aiohttp.ClientSession(loop=loop) as session:
        for i in range(20):
            try:
                async with session.get('http://localhost:8000/') as r:
                    assert r.status == 200
                    assert (await r.text()) == 'hello world'
            except (AssertionError, OSError):
                await asyncio.sleep(0.1, loop=loop)
            else:
                app_running = True
                break
    assert app_running

    assert len(observer._handlers) == 1
    event_handlers = list(observer._handlers.values())[0]
    assert len(event_handlers) == 2
    code_event_handler = next(eh for eh in event_handlers if isinstance(eh, PyCodeEventHandler))
    code_event_handler._process.terminate()


async def test_run_app(loop, tmpworkdir, test_client):
    mktree(tmpworkdir, SIMPLE_APP)
    app = create_main_app(app_path='app.py', loop=loop)
    assert isinstance(app, aiohttp.web.Application)
    cli = await test_client(app)
    r = await cli.get('/')
    assert r.status == 200
    text = await r.text()
    assert text == 'hello world'
