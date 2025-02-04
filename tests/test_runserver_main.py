import asyncio
import json
import ssl
from unittest import mock

import aiohttp
import pytest
from aiohttp import ClientTimeout
from pytest_toolbox import mktree

from multiprocessing import set_start_method

from aiohttp_devtools.runserver import runserver
from aiohttp_devtools.runserver.config import Config
from aiohttp_devtools.runserver.serve import (
    WS, create_auxiliary_app, create_main_app, modify_main_app, src_reload, start_main_app)
from aiohttp_devtools.runserver.watch import AppTask

from .conftest import SIMPLE_APP, forked, linux_forked


async def check_server_running(check_callback):
    port_open = False
    async with aiohttp.ClientSession(timeout=ClientTimeout(total=1)) as session:
        for i in range(50):  # pragma: no branch
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
    args = runserver(app_path="app.py", static_path="static_dir", bind_address="0.0.0.0")
    aux_app = args["app"]
    aux_port = args["port"]
    runapp_host = args["host"]
    assert isinstance(aux_app, aiohttp.web.Application)
    assert aux_port == 8001
    assert runapp_host == "0.0.0.0"
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
def test_start_runserver_app_instance(tmpworkdir):
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
    runapp_host = args["host"]
    assert isinstance(aux_app, aiohttp.web.Application)
    assert aux_port == 8001
    assert runapp_host == "localhost"
    assert len(aux_app.on_startup) == 1
    assert len(aux_app.on_shutdown) == 1
    assert len(aux_app.cleanup_ctx) == 1


@forked
async def test_start_runserver_with_multi_app_modules(tmpworkdir, capfd):
    mktree(tmpworkdir, {
        "app.py": f"""\
from aiohttp import web
import sys
sys.path.insert(0, "{tmpworkdir}/libs/l1")

async def hello(request):
    return web.Response(text="<h1>hello world</h1>", content_type="text/html")

async def create_app():
    a = web.Application()
    a.router.add_get("/", hello)
    return a
""",
        "libs": {
            "l1": {
                "__init__.py": "",
                "app.py": "print('wrong_import')"
            }
        }
    })

    set_start_method("spawn")
    config = Config(app_path="app.py", root_path=tmpworkdir, main_port=0, app_factory_name="create_app")
    module = config.import_module()
    config.get_app_factory(module)
    app_task = AppTask(config)

    app_task._start_dev_server()
    try:
        app_task._process.join(2)

        captured = capfd.readouterr()
        assert captured.out == ""
    finally:
        await app_task._stop_dev_server()


@forked
async def test_run_app_aiohttp_client(tmpworkdir, aiohttp_client):
    mktree(tmpworkdir, SIMPLE_APP)
    config = Config(app_path='app.py')
    module = config.import_module()
    app_factory = config.get_app_factory(module)
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
    module = config.import_module()
    app_factory = config.get_app_factory(module)
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
async def test_serve_main_app(tmpworkdir, mocker):
    loop = asyncio.get_running_loop()
    mktree(tmpworkdir, SIMPLE_APP)
    mock_modify_main_app = mocker.patch('aiohttp_devtools.runserver.serve.modify_main_app')
    loop.call_later(0.5, loop.stop)

    config = Config(app_path="app.py", main_port=0)
    module = config.import_module()
    runner = await create_main_app(config, config.get_app_factory(module))
    await start_main_app(runner, config.bind_address, config.main_port, None)

    mock_modify_main_app.assert_called_with(mock.ANY, config)

    await runner.cleanup()


@forked
async def test_start_main_app_app_instance(tmpworkdir, mocker):
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
    module = config.import_module()
    runner = await create_main_app(config, config.get_app_factory(module))
    await start_main_app(runner, config.bind_address, config.main_port, None)

    mock_modify_main_app.assert_called_with(mock.ANY, config)

    await runner.cleanup()


@pytest.fixture
async def aux_cli(aiohttp_client):
    app = create_auxiliary_app(static_path='.')
    async with await aiohttp_client(app) as cli:
        yield cli


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


async def test_websocket_info(aux_cli):
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


async def test_websocket_reload(aux_cli):
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


async def check_ssl_server_running(check_callback):
    port_open = False
    ssl_context = ssl.create_default_context()
    ssl_context.load_verify_locations("test_certs/rootCA.pem")

    async with aiohttp.ClientSession(timeout=ClientTimeout(total=1)) as session:
        for i in range(50):  # pragma: no branch
            try:
                async with session.get("https://localhost:8000/", ssl=ssl_context):
                    pass
            except OSError:
                await asyncio.sleep(0.1)
            else:
                port_open = True
                break
        assert port_open
        await check_callback(session, ssl_context)
    await asyncio.sleep(.25)  # TODO(aiohttp 4): Remove this hack


@pytest.mark.filterwarnings(r"ignore:unclosed:ResourceWarning")
@linux_forked
@pytest.mark.datafiles("tests/test_certs", keep_top_dir=True)
def test_start_runserver_ssl(datafiles, tmpworkdir, smart_caplog):
    mktree(tmpworkdir, {
        "app.py": """\
from aiohttp import web
import ssl
async def hello(request):
    return web.Response(text="<h1>hello world</h1>", content_type="text/html")

async def has_error(request):
    raise ValueError()

def create_app():
    app = web.Application()
    app.router.add_get("/", hello)
    app.router.add_get("/error", has_error)
    return app

def get_ssl_context():
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain("test_certs/server.crt", "test_certs/server.key")
    return ssl_context
    """,
        "static_dir/foo.js": "var bar=1;",
    })
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    args = runserver(app_path="app.py", static_path="static_dir",
                     bind_address="0.0.0.0", ssl_context_factory_name="get_ssl_context")
    aux_app = args["app"]
    aux_port = args["port"]
    runapp_host = args["host"]
    assert isinstance(aux_app, aiohttp.web.Application)
    assert aux_port == 8001
    assert runapp_host == "0.0.0.0"
    for startup in aux_app.on_startup:
        loop.run_until_complete(startup(aux_app))

    async def check_callback(session, ssl_context):
        print(session, ssl_context)
        async with session.get("https://localhost:8000/", ssl=ssl_context) as r:
            assert r.status == 200
            assert r.headers["content-type"].startswith("text/html")
            text = await r.text()
            print(text)
            assert "<h1>hello world</h1>" in text
            assert '<script src="http://localhost:8001/livereload.js"></script>' in text

        async with session.get("https://localhost:8000/error", ssl=ssl_context) as r:
            assert r.status == 500
            assert "raise ValueError()" in (await r.text())

    try:
        loop.run_until_complete(check_ssl_server_running(check_callback))
    finally:
        for shutdown in aux_app.on_shutdown:
            loop.run_until_complete(shutdown(aux_app))
        loop.run_until_complete(aux_app.cleanup())
    assert (
        "adev.server.dft INFO: Starting aux server at http://localhost:8001 ◆\n"
        "adev.server.dft INFO: serving static files from ./static_dir/ at http://localhost:8001/static/\n"
        "adev.server.dft INFO: Starting dev server at https://localhost:8000 ●\n"
    ) in smart_caplog
    loop.run_until_complete(asyncio.sleep(.25))  # TODO(aiohttp 4): Remove this hack
