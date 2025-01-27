import asyncio

import aiohttp
import pytest
from aiohttp import ClientTimeout
from pytest_toolbox import mktree
import ssl

from aiohttp_devtools.runserver import runserver
from aiohttp_devtools.runserver.config import Config

from aiohttp_devtools.exceptions import AiohttpDevConfigError

from .conftest import forked


async def test_load_invalid_app(tmpworkdir):
    mktree(tmpworkdir, {
        'invalid': "it's not python file)"
    })
    with pytest.raises(AiohttpDevConfigError):
        Config(app_path='invalid')

async def check_server_running(check_callback, sslcontext):
    port_open = False
    async with aiohttp.ClientSession(timeout=ClientTimeout(total=1)) as session:
        for i in range(50):  # pragma: no branch
            try:
                async with session.get('https://localhost:8443/', ssl=sslcontext):
                    pass
            except OSError:
                await asyncio.sleep(0.1)
            else:
                port_open = True
                break
        assert port_open
        await check_callback(session, sslcontext)
    await asyncio.sleep(.25)  # TODO(aiohttp 4): Remove this hack

@pytest.mark.filterwarnings(r"ignore:unclosed:ResourceWarning")
@forked
@pytest.mark.datafiles('tests/test_certs', keep_top_dir = True)
def test_start_runserver_ssl(datafiles, tmpworkdir, smart_caplog):
    mktree(tmpworkdir, {
        'app.py': """\
from aiohttp import web
import ssl
async def hello(request):
    return web.Response(text='<h1>hello world</h1>', content_type='text/html')

async def has_error(request):
    raise ValueError()

def create_app():
    app = web.Application()
    app.router.add_get('/', hello)
    app.router.add_get('/error', has_error)
    return app

def get_ssl_context():
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain('test_certs/server.crt', 'test_certs/server.key')
    return ssl_context
    """,
        'static_dir/foo.js': 'var bar=1;',
    })
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    args = runserver(app_path="app.py", static_path="static_dir", bind_address="0.0.0.0", ssl_context_factory_name='get_ssl_context')
    aux_app = args["app"]
    aux_port = args["port"]
    runapp_host = args["host"]
    assert isinstance(aux_app, aiohttp.web.Application)
    assert aux_port == 8444
    assert runapp_host == "0.0.0.0"
    for startup in aux_app.on_startup:
        loop.run_until_complete(startup(aux_app))
    sslcontext = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    async def check_callback(session, sslcontext):
        print(session, sslcontext)
        async with session.get('https://localhost:8443/', ssl=sslcontext) as r:
            assert r.status == 200
            assert r.headers['content-type'].startswith('text/html')
            text = await r.text()
            print(text)
            assert '<h1>hello world</h1>' in text
            assert '<script src="https://localhost:8444/livereload.js"></script>' in text

        async with session.get('https://localhost:8443/error', ssl=sslcontext) as r:
            assert r.status == 500
            assert 'raise ValueError()' in (await r.text())

    try:
        loop.run_until_complete(check_server_running(check_callback, sslcontext))
    finally:
        for shutdown in aux_app.on_shutdown:
            loop.run_until_complete(shutdown(aux_app))
        loop.run_until_complete(aux_app.cleanup())
    assert (
        'adev.server.dft INFO: Starting aux server at https://localhost:8444 ◆\n'
        'adev.server.dft INFO: serving static files from ./static_dir/ at https://localhost:8444/static/\n'
        'adev.server.dft INFO: Starting dev server at https://localhost:8443 ●\n'
    ) in smart_caplog
    loop.run_until_complete(asyncio.sleep(.25))  # TODO(aiohttp 4): Remove this hack


