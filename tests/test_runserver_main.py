import asyncio
import json
import os
import signal
import time
from multiprocessing import Process
from unittest import mock

import aiohttp
import pytest
from aiohttp.web import Application
from pytest_toolbox import mktree

from aiohttp_devtools.runserver import run_app, runserver
from aiohttp_devtools.runserver.config import Config
from aiohttp_devtools.runserver.serve import create_auxiliary_app, modify_main_app, serve_main_app

from .conftest import SIMPLE_APP, get_if_boxed, get_slow

slow = get_slow(pytest)
if_boxed = get_if_boxed(pytest)


async def check_server_running(loop, check_callback):
    port_open = False
    for i in range(50):
        try:
            await loop.create_connection(lambda: asyncio.Protocol(), host='localhost', port=8000)
        except OSError:
            await asyncio.sleep(0.1, loop=loop)
        else:
            port_open = True
            break
    assert port_open

    async with aiohttp.ClientSession(loop=loop) as session:
        await check_callback(session)


@if_boxed
@slow
def test_start_runserver(tmpworkdir, caplog):
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
    aux_app, aux_port, _ = runserver(app_path='app.py', static_path='static_dir')
    assert isinstance(aux_app, aiohttp.web.Application)
    assert aux_port == 8001
    start_app = aux_app.on_startup[0]
    stop_app = aux_app.on_shutdown[0]
    loop.run_until_complete(start_app(aux_app))

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
        loop.run_until_complete(check_server_running(loop, check_callback))
    finally:
        loop.run_until_complete(stop_app(aux_app))
    assert (
        'adev.server.dft INFO: pre-check enabled, checking app factory\n'
        'adev.server.dft INFO: Starting aux server at http://localhost:8001 ◆\n'
        'adev.server.dft INFO: serving static files from ./static_dir/ at http://localhost:8001/static/\n'
        'adev.server.dft INFO: Starting dev server at http://localhost:8000 ●\n'
    ) == caplog


@if_boxed
@slow
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
    asyncio.set_event_loop(loop)
    aux_app, aux_port, _ = runserver(app_path='app.py', host='foobar.com')
    assert isinstance(aux_app, aiohttp.web.Application)
    assert aux_port == 8001
    assert len(aux_app.on_startup) == 1
    assert len(aux_app.on_shutdown) == 1


@if_boxed
@slow
def test_start_runserver_no_loop_argument(tmpworkdir, loop):
    mktree(tmpworkdir, {
        'app.py': """\
from aiohttp import web

async def hello(request):
    return web.Response(text='<h1>hello world</h1>', content_type='text/html')

def app():
    a = web.Application()
    a.router.add_get('/', hello)
    return a
"""
    })
    asyncio.set_event_loop(loop)
    aux_app, aux_port, _ = runserver(app_path='app.py')
    assert isinstance(aux_app, aiohttp.web.Application)
    assert aux_port == 8001
    assert len(aux_app.on_startup) == 1
    assert len(aux_app.on_shutdown) == 1


def kill_parent_soon(pid):
    time.sleep(0.2)
    os.kill(pid, signal.SIGINT)


@if_boxed
@slow
def test_run_app(loop, unused_port):
    app = Application()
    port = unused_port()
    Process(target=kill_parent_soon, args=(os.getpid(),)).start()
    run_app(app, port, loop)


@if_boxed
async def test_run_app_test_client(loop, tmpworkdir, test_client):
    mktree(tmpworkdir, SIMPLE_APP)
    config = Config(app_path='app.py')
    app = config.app_factory(loop=loop)
    modify_main_app(app, config)
    assert isinstance(app, aiohttp.web.Application)
    cli = await test_client(app)
    r = await cli.get('/')
    assert r.status == 200
    text = await r.text()
    assert text == 'hello world'


async def test_aux_app(tmpworkdir, test_client):
    mktree(tmpworkdir, {
        'test.txt': 'test value',
    })
    app = create_auxiliary_app(static_path='.')
    cli = await test_client(app)
    r = await cli.get('/test.txt')
    assert r.status == 200
    text = await r.text()
    assert text == 'test value'


@if_boxed
@slow
def test_serve_main_app(tmpworkdir, loop, mocker):
    mktree(tmpworkdir, SIMPLE_APP)
    mocker.spy(loop, 'create_server')
    mock_modify_main_app = mocker.patch('aiohttp_devtools.runserver.serve.modify_main_app')
    loop.call_later(0.5, loop.stop)

    config = Config(app_path='app.py')
    serve_main_app(config, loop=loop)

    assert loop.is_closed()
    loop.create_server.assert_called_with(mock.ANY, '0.0.0.0', 8000, backlog=128)
    mock_modify_main_app.assert_called_with(mock.ANY, config)


@if_boxed
@slow
def test_serve_main_app_app_instance(tmpworkdir, loop, mocker):
    mktree(tmpworkdir, {
        'app.py': """\
from aiohttp import web

async def hello(request):
    return web.Response(text='<h1>hello world</h1>', content_type='text/html')

app = web.Application()
app.router.add_get('/', hello)
"""
    })
    asyncio.set_event_loop(loop)
    mocker.spy(loop, 'create_server')
    mock_modify_main_app = mocker.patch('aiohttp_devtools.runserver.serve.modify_main_app')
    loop.call_later(0.5, loop.stop)

    config = Config(app_path='app.py')
    serve_main_app(config)

    assert loop.is_closed()
    loop.create_server.assert_called_with(mock.ANY, '0.0.0.0', 8000, backlog=128)
    mock_modify_main_app.assert_called_with(mock.ANY, config)


@pytest.fixture
def aux_cli(test_client, loop):
    app = create_auxiliary_app(static_path='.')
    return loop.run_until_complete(test_client(app))


async def test_websocket_hello(aux_cli, caplog):
    async with aux_cli.session.ws_connect(aux_cli.make_url('/livereload')) as ws:
        ws.send_json({'command': 'hello', 'protocols': ['http://livereload.com/protocols/official-7']})
        async for msg in ws:
            assert msg.tp == aiohttp.WSMsgType.text
            data = json.loads(msg.data)
            assert data == {
                'serverName': 'livereload-aiohttp',
                'command': 'hello',
                'protocols': ['http://livereload.com/protocols/official-7']
            }
            break  # noqa
    assert 'adev.server.aux WARNING: browser disconnected, appears no websocket connection was made' in caplog


async def test_websocket_info(aux_cli, loop):
    assert len(aux_cli.server.app['websockets']) == 0
    ws = await aux_cli.session.ws_connect(aux_cli.make_url('/livereload'))
    try:
        ws.send_json({'command': 'info', 'url': 'foobar', 'plugins': 'bang'})
        await asyncio.sleep(0.05, loop=loop)
        assert len(aux_cli.server.app['websockets']) == 1
    finally:
        await ws.close()


async def test_websocket_bad(aux_cli, caplog):
    async with aux_cli.session.ws_connect(aux_cli.make_url('/livereload')) as ws:
        ws.send_str('not json')
        ws.send_json({'command': 'hello', 'protocols': ['not official-7']})
        ws.send_json({'command': 'boom', 'url': 'foobar', 'plugins': 'bang'})
        ws.send_bytes(b'this is bytes')
    assert 'adev.server.aux ERROR: live reload protocol 7 not supported' in caplog.log
    assert 'adev.server.aux ERROR: JSON decode error' in caplog.log
    assert 'adev.server.aux ERROR: Unknown ws message' in caplog.log
    assert "adev.server.aux ERROR: unknown websocket message type binary, data: b'this is bytes'" in caplog


async def test_websocket_reload(aux_cli, loop):
    assert aux_cli.server.app.src_reload('foobar') == 0
    ws = await aux_cli.session.ws_connect(aux_cli.make_url('/livereload'))
    try:
        ws.send_json({
            'command': 'info',
            'url': 'foobar',
            'plugins': 'bang',
        })
        await asyncio.sleep(0.05, loop=loop)
        assert aux_cli.server.app.src_reload('foobar') == 1
    finally:
        await ws.close()
