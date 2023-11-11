import asyncio
import json
from unittest import mock

import aiohttp
import pytest
from aiohttp import ClientTimeout
from pytest_toolbox import mktree

from aiohttp_devtools.runserver import runserver
from aiohttp_devtools.runserver.config import Config
from aiohttp_devtools.runserver.serve import (
    WS, create_auxiliary_app, create_main_app, modify_main_app, src_reload, start_main_app)

from .conftest import SIMPLE_APP, forked


async def check_server_running(check_callback):
    port_open = False
    async with aiohttp.ClientSession(timeout=ClientTimeout(total=1)) as session:
        for i in range(50):
            try:
                async with session.get('http://localhost:8000/'):
                    pass
            except OSError:
                await asyncio.sleep(0.1)
            else:
                port_open = True
                break
        assert port_open
        await check_callback(session)
    await asyncio.sleep(.25)  # TODO(aiohttp 4): Remove this hack


# TODO: Can't find a way to fix these warnings, maybe fixed in aiohttp 4.
@pytest.mark.filterwarnings(r"ignore:unclosed:ResourceWarning")
@forked
def test_start_runserver(tmpworkdir, smart_caplog):
    mktree(tmpworkdir, {
        'app.py': """\
from aiohttp import web

async def hello(request):
    return web.Response(text='<h1>hello world</h1>', content_type='text/html')

async def has_error(request):
    raise ValueError()

def create_app():
    app = web.Application()
    app.router.add_get('/', hello)
    app.router.add_get('/error', has_error)
    return app""",
        'static_dir/foo.js': 'var bar=1;',
    })
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    args = runserver(app_path='app.py', static_path='static_dir')
    aux_app = args["app"]
    aux_port = args["port"]
    assert isinstance(aux_app, aiohttp.web.Application)
    assert aux_port == 8001
    for startup in aux_app.on_startup:
        loop.run_until_complete(startup(aux_app))

    async def check_callback(session):
        async with session.get('http://localhost:8000/') as r:
            assert r.status == 200
            assert r.headers['content-type'].startswith('text/html')
            text = await r.text()
            assert '<h1>hello world</h1>' in text
            assert '<script src="http://localhost:8001/livereload.js"></script>' in text

        async with session.get('http://localhost:8000/error') as r:
            assert r.status == 500
            assert 'raise ValueError()' in (await r.text())

    try:
        loop.run_until_complete(check_server_running(check_callback))
    finally:
        for shutdown in aux_app.on_shutdown:
            loop.run_until_complete(shutdown(aux_app))
        loop.run_until_complete(aux_app.cleanup())
    assert (
        'adev.server.dft INFO: Starting aux server at http://localhost:8001 ◆\n'
        'adev.server.dft INFO: serving static files from ./static_dir/ at http://localhost:8001/static/\n'
        'adev.server.dft INFO: Starting dev server at http://localhost:8000 ●\n'
    ) in smart_caplog
    loop.run_until_complete(asyncio.sleep(.25))  # TODO(aiohttp 4): Remove this hack


@forked
def test_start_runserver_app_instance(tmpworkdir, event_loop):
    mktree(tmpworkdir, {
        'app.py': """\
from aiohttp import web

async def hello(request):
    return web.Response(text='<h1>hello world</h1>', content_type='text/html')

app = web.Application()
app.router.add_get('/', hello)
"""
    })
    args = runserver(app_path="app.py", host="foobar.com", main_port=0, aux_port=8001)
    aux_app = args["app"]
    aux_port = args["port"]
    assert isinstance(aux_app, aiohttp.web.Application)
    assert aux_port == 8001
    assert len(aux_app.on_startup) == 1
    assert len(aux_app.on_shutdown) == 1
    assert len(aux_app.cleanup_ctx) == 1


@forked
async def test_run_app_aiohttp_client(tmpworkdir, aiohttp_client):
    mktree(tmpworkdir, SIMPLE_APP)
    config = Config(app_path='app.py')
    app_factory = config.import_app_factory()
    app = await config.load_app(app_factory)
    modify_main_app(app, config)
    assert isinstance(app, aiohttp.web.Application)
    cli = await aiohttp_client(app)
    r = await cli.get('/')
    assert r.status == 200
    assert r.headers["Cache-Control"] == "no-cache"
    text = await r.text()
    assert text == 'hello world'


@forked
async def test_run_app_browser_cache(tmpworkdir, aiohttp_client):
    mktree(tmpworkdir, SIMPLE_APP)
    config = Config(app_path="app.py", browser_cache=True)
    app_factory = config.import_app_factory()
    app = await config.load_app(app_factory)
    modify_main_app(app, config)
    cli = await aiohttp_client(app)
    r = await cli.get("/")
    assert r.status == 200
    assert "Cache-Control" not in r.headers


async def test_aux_app(tmpworkdir, aiohttp_client):
    mktree(tmpworkdir, {
        'test.txt': 'test value',
    })
    app = create_auxiliary_app(static_path='.')
    async with await aiohttp_client(app) as cli:
        async with cli.get('/test.txt') as r:
            assert r.status == 200
            text = await r.text()
    assert text == 'test value'
    await asyncio.sleep(0)  # TODO(aiohttp 4): Remove this hack


@forked
async def test_serve_main_app(tmpworkdir, event_loop, mocker):
    asyncio.set_event_loop(event_loop)
    mktree(tmpworkdir, SIMPLE_APP)
    mock_modify_main_app = mocker.patch('aiohttp_devtools.runserver.serve.modify_main_app')
    event_loop.call_later(0.5, event_loop.stop)

    config = Config(app_path="app.py", main_port=0)
    runner = await create_main_app(config, config.import_app_factory())
    await start_main_app(runner, config.main_port)

    mock_modify_main_app.assert_called_with(mock.ANY, config)

    await runner.cleanup()


@forked
async def test_start_main_app_app_instance(tmpworkdir, event_loop, mocker):
    mktree(tmpworkdir, {
        'app.py': """\
from aiohttp import web

async def hello(request):
    return web.Response(text='<h1>hello world</h1>', content_type='text/html')

app = web.Application()
app.router.add_get('/', hello)
"""
    })
    mock_modify_main_app = mocker.patch('aiohttp_devtools.runserver.serve.modify_main_app')

    config = Config(app_path="app.py", main_port=0)
    runner = await create_main_app(config, config.import_app_factory())
    await start_main_app(runner, config.main_port)

    mock_modify_main_app.assert_called_with(mock.ANY, config)

    await runner.cleanup()


@pytest.fixture
def aux_cli(aiohttp_client, event_loop):
    app = create_auxiliary_app(static_path='.')
    cli = event_loop.run_until_complete(aiohttp_client(app))
    yield cli
    event_loop.run_until_complete(cli.close())


async def test_websocket_hello(aux_cli, smart_caplog):
    async with aux_cli.session.ws_connect(aux_cli.make_url('/livereload')) as ws:
        await ws.send_json({'command': 'hello', 'protocols': ['http://livereload.com/protocols/official-7']})
        async for msg in ws:
            assert msg.type == aiohttp.WSMsgType.text
            data = json.loads(msg.data)
            assert data == {
                'serverName': 'livereload-aiohttp',
                'command': 'hello',
                'protocols': ['http://livereload.com/protocols/official-7']
            }
            break  # noqa
    assert 'adev.server.aux WARNING: browser disconnected, appears no websocket connection was made' in smart_caplog


async def test_websocket_info(aux_cli, event_loop):
    assert len(aux_cli.server.app[WS]) == 0
    ws = await aux_cli.session.ws_connect(aux_cli.make_url('/livereload'))
    try:
        await ws.send_json({'command': 'info', 'url': 'foobar', 'plugins': 'bang'})
        await asyncio.sleep(0.05)
        assert len(aux_cli.server.app[WS]) == 1
    finally:
        await ws.close()


async def test_websocket_bad(aux_cli, smart_caplog):
    async with aux_cli.session.ws_connect(aux_cli.make_url('/livereload')) as ws:
        await ws.send_str('not json')
    async with aux_cli.session.ws_connect(aux_cli.make_url('/livereload')) as ws:
        await ws.send_json({'command': 'hello', 'protocols': ['not official-7']})
    async with aux_cli.session.ws_connect(aux_cli.make_url('/livereload')) as ws:
        await ws.send_json({'command': 'boom', 'url': 'foobar', 'plugins': 'bang'})
    async with aux_cli.session.ws_connect(aux_cli.make_url('/livereload')) as ws:
        await ws.send_bytes(b'this is bytes')
    assert 'adev.server.aux ERROR: live reload protocol 7 not supported' in smart_caplog.log
    assert 'adev.server.aux ERROR: JSON decode error' in smart_caplog.log
    assert 'adev.server.aux ERROR: Unknown ws message' in smart_caplog.log
    assert "adev.server.aux ERROR: unknown websocket message type binary, data: b'this is bytes'" in smart_caplog


async def test_websocket_reload(aux_cli, event_loop):
    reloads = await src_reload(aux_cli.server.app, 'foobar')
    assert reloads == 0
    ws = await aux_cli.session.ws_connect(aux_cli.make_url('/livereload'))
    try:
        await ws.send_json({
            'command': 'info',
            'url': 'foobar',
            'plugins': 'bang',
        })
        await asyncio.sleep(0.05)
        reloads = await src_reload(aux_cli.server.app, 'foobar')
        assert reloads == 1
    finally:
        await ws.close()
