import asyncio
import json
import os
import signal
import time
from multiprocessing import Process
from unittest import mock

import aiohttp
import pytest
from aiohttp import ClientTimeout
from aiohttp.web import Application
from aiohttp.web_log import AccessLogger
from pytest_toolbox import mktree

from aiohttp_devtools.runserver import run_app, runserver
from aiohttp_devtools.runserver.config import Config
from aiohttp_devtools.runserver.serve import create_auxiliary_app, modify_main_app, src_reload, start_main_app

from .conftest import SIMPLE_APP


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


@pytest.mark.boxed
def test_start_runserver(tmpworkdir, smart_caplog):
    mktree(tmpworkdir, {
        'app.py': """\
from aiohttp import web

async def hello(request):
    return web.Response(text='<h1>hello world</h1>', content_type='text/html')

async def has_error(request):
    raise ValueError()

def create_app(loop):
    app = web.Application()
    app.router.add_get('/', hello)
    app.router.add_get('/error', has_error)
    return app""",
        'static_dir/foo.js': 'var bar=1;',
    })
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    aux_app, aux_port, _, _ = runserver(app_path='app.py', static_path='static_dir')
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
    assert (
        'adev.server.dft INFO: Starting aux server at http://localhost:8001 ◆\n'
        'adev.server.dft INFO: serving static files from ./static_dir/ at http://localhost:8001/static/\n'
        'adev.server.dft INFO: Starting dev server at http://localhost:8000 ●\n'
    ) in smart_caplog


@pytest.mark.boxed
def test_start_runserver_app_instance(tmpworkdir, loop):
    mktree(tmpworkdir, {
        'app.py': """\
from aiohttp import web

async def hello(request):
    return web.Response(text='<h1>hello world</h1>', content_type='text/html')

app = web.Application()
app.router.add_get('/', hello)
"""
    })
    aux_app, aux_port, _, _ = runserver(app_path='app.py', host='foobar.com')
    assert isinstance(aux_app, aiohttp.web.Application)
    assert aux_port == 8001
    assert len(aux_app.on_startup) == 2
    assert len(aux_app.on_shutdown) == 2


def kill_parent_soon(pid):
    time.sleep(0.2)
    os.kill(pid, signal.SIGINT)


@pytest.mark.boxed
def test_run_app(loop, aiohttp_unused_port):
    app = Application()
    port = aiohttp_unused_port()
    Process(target=kill_parent_soon, args=(os.getpid(),)).start()
    run_app(app, port, loop, AccessLogger)


@pytest.mark.boxed
async def test_run_app_aiohttp_client(tmpworkdir, aiohttp_client):
    mktree(tmpworkdir, SIMPLE_APP)
    config = Config(app_path='app.py')
    app_factory = config.import_app_factory()
    app = app_factory()
    modify_main_app(app, config)
    assert isinstance(app, aiohttp.web.Application)
    cli = await aiohttp_client(app)
    r = await cli.get('/')
    assert r.status == 200
    text = await r.text()
    assert text == 'hello world'


async def test_aux_app(tmpworkdir, aiohttp_client):
    mktree(tmpworkdir, {
        'test.txt': 'test value',
    })
    app = create_auxiliary_app(static_path='.')
    cli = await aiohttp_client(app)
    r = await cli.get('/test.txt')
    assert r.status == 200
    text = await r.text()
    assert text == 'test value'


@pytest.mark.boxed
async def test_serve_main_app(tmpworkdir, loop, mocker):
    asyncio.set_event_loop(loop)
    mktree(tmpworkdir, SIMPLE_APP)
    mock_modify_main_app = mocker.patch('aiohttp_devtools.runserver.serve.modify_main_app')
    loop.call_later(0.5, loop.stop)

    config = Config(app_path='app.py')
    runner = await create_main_app(config, config.import_app_factory(), loop)
    await start_main_app(runner, config.main_port)

    mock_modify_main_app.assert_called_with(mock.ANY, config)


@pytest.mark.boxed
async def test_start_main_app_app_instance(tmpworkdir, loop, mocker):
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

    config = Config(app_path='app.py')
    runner = await create_main_app(config, config.import_app_factory(), loop)
    await start_main_app(runner, config.main_port)

    mock_modify_main_app.assert_called_with(mock.ANY, config)


@pytest.yield_fixture
def aux_cli(aiohttp_client, loop):
    app = create_auxiliary_app(static_path='.')
    cli = loop.run_until_complete(aiohttp_client(app))
    yield cli
    loop.run_until_complete(cli.close())


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


async def test_websocket_info(aux_cli, loop):
    assert len(aux_cli.server.app['websockets']) == 0
    ws = await aux_cli.session.ws_connect(aux_cli.make_url('/livereload'))
    try:
        await ws.send_json({'command': 'info', 'url': 'foobar', 'plugins': 'bang'})
        await asyncio.sleep(0.05)
        assert len(aux_cli.server.app['websockets']) == 1
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


async def test_websocket_reload(aux_cli, loop):
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
