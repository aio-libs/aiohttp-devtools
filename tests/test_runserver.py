from aiohttp import web
from aiohttp_devtools.runserver import runserver
from aiohttp_devtools.runserver.serve import create_main_app
from aiohttp_devtools.runserver.watch import PyCodeEventHandler

from .conftest import mktree


async def test_start_runserver(loop, tmpworkdir):
    mktree(tmpworkdir, {
        'app.py': """\
from aiohttp import web

async def hello(request):
    return web.Response(text='hello world')

def create_app(loop):
    app = web.Application(loop=loop)
    app.router.add_get('/', hello)
    return app""",
    })
    aux_app, observer, aux_port = runserver(app_path='app.py', loop=loop)
    assert aux_port == 8001
    event_handlers = list(observer._handlers.values())[0]
    assert len(event_handlers) == 2
    code_event_handler = next(eh for eh in event_handlers if isinstance(eh, PyCodeEventHandler))
    code_event_handler._process.terminate()


async def test_run_app(loop, tmpworkdir, test_client):
    mktree(tmpworkdir, {
        'app.py': """\
from aiohttp import web

async def hello(request):
    return web.Response(text='hello world')

def create_app(loop):
    app = web.Application(loop=loop)
    app.router.add_get('/', hello)
    return app""",
    })
    app = create_main_app(app_path='app.py', loop=loop)
    assert isinstance(app, web.Application)
    cli = await test_client(app)
    r = await cli.get('/')
    assert r.status == 200
    text = await r.text()
    assert text == 'hello world'

