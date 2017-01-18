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
from aiohttp_devtools.runserver.serve import create_auxiliary_app, create_main_app, serve_main_app
from aiohttp_devtools.runserver.watch import PyCodeEventHandler

from .conftest import SIMPLE_APP, get_if_boxed, get_slow

slow = get_slow(pytest)
if_boxed = get_if_boxed(pytest)


async def check_server_running(loop):
    async with aiohttp.ClientSession(loop=loop) as session:
        for i in range(30):
            try:
                async with session.get('http://localhost:8000/') as r:
                    assert r.status == 200
                    assert (await r.text()) == 'hello world'
            except (AssertionError, OSError):
                await asyncio.sleep(0.1, loop=loop)
            else:
                async with session.get('http://localhost:8000/error') as r:
                    assert r.status == 500
                    assert 'raise ValueError()' in (await r.text())
                return True


@if_boxed
@slow
def test_start_runserver(tmpworkdir, caplog):
    mktree(tmpworkdir, {
        'app.py': """\
from aiohttp import web

async def hello(request):
    return web.Response(text='hello world')

async def has_error(request):
    raise ValueError()

def create_app(loop):
    app = web.Application(loop=loop)
    app.router.add_get('/', hello)
    app.router.add_get('/error', has_error)
    return app""",
        'static_dir/foo.js': 'var bar=1;',
    })
    loop = asyncio.new_event_loop()
    aux_app, observer, aux_port = runserver(app_path='app.py', loop=loop, static_path='static_dir')
    assert isinstance(aux_app, aiohttp.web.Application)
    assert aux_port == 8001

    assert loop.run_until_complete(check_server_running(loop))

    assert len(observer._handlers) == 2
    event_handlers = next(eh for eh in observer._handlers.values() if len(eh) == 2)
    code_event_handler = next(eh for eh in event_handlers if isinstance(eh, PyCodeEventHandler))
    code_event_handler._process.terminate()
    assert (
        'adev.server.dft INFO: pre-check enabled, checking app factory\n'
        'adev.server.dft INFO: Starting dev server at http://localhost:8000 ●\n'
        'adev.server.dft INFO: Starting aux server at http://localhost:8001 ◆\n'
        'adev.server.dft INFO: serving static files from ./static_dir/ at http://localhost:8001/static/\n'
    ) == caplog


def kill_parent_soon():
    time.sleep(0.2)
    os.kill(os.getppid(), signal.SIGINT)


@if_boxed
@slow
def test_run_app(loop, unused_port):
    app = Application(loop=loop)
    obersver = mock.MagicMock()
    port = unused_port()
    Process(target=kill_parent_soon).start()
    run_app(app, obersver, port)


async def test_run_app_test_client(loop, tmpworkdir, test_client):
    mktree(tmpworkdir, SIMPLE_APP)
    app = create_main_app(Config(app_path='app.py'), loop=loop)
    assert isinstance(app, aiohttp.web.Application)
    cli = await test_client(app)
    r = await cli.get('/')
    assert r.status == 200
    text = await r.text()
    assert text == 'hello world'


async def test_aux_app(loop, tmpworkdir, test_client):
    mktree(tmpworkdir, {
        'test.txt': 'test value',
    })
    app = create_auxiliary_app(static_path='.', port=8000, loop=loop)
    cli = await test_client(app)
    r = await cli.get('/test.txt')
    assert r.status == 200
    text = await r.text()
    assert text == 'test value'


@if_boxed
@slow
def test_run_app_http(tmpworkdir, loop, mocker):
    mktree(tmpworkdir, SIMPLE_APP)
    mocker.spy(loop, 'create_server')
    mock_modify_main_app = mocker.patch('aiohttp_devtools.runserver.serve.modify_main_app')
    loop.call_later(0.5, loop.stop)

    config = Config(app_path='app.py')
    serve_main_app(config, loop=loop)

    assert loop.is_closed()
    loop.create_server.assert_called_with(mock.ANY, '0.0.0.0', 8000, backlog=128)
    mock_modify_main_app.assert_called_with(mock.ANY, config)


@pytest.fixture
def aux_cli(test_client, loop):
    app = create_auxiliary_app(static_path='.', port=8000, loop=loop)
    return loop.run_until_complete(test_client(app))


async def test_websocket_hello(aux_cli, caplog):
    async with aux_cli.session.ws_connect(aux_cli.make_url('/livereload')) as ws:
        ws.send_json({'command': 'hello', 'protocols': ['http://livereload.com/protocols/official-7']})
        async for msg in ws:
            assert msg.tp == aiohttp.MsgType.text
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
