import pytest
from aiohttp import web
from pytest_toolbox import mktree

from aiohttp_devtools.exceptions import AiohttpDevConfigError
from aiohttp_devtools.runserver.config import Config

from .conftest import SIMPLE_APP, get_if_boxed

if_boxed = get_if_boxed(pytest)


async def test_load_simple_app(tmpworkdir):
    mktree(tmpworkdir, SIMPLE_APP)
    Config(app_path='app.py')


async def test_create_app_wrong_name(tmpworkdir, loop):
    mktree(tmpworkdir, SIMPLE_APP)
    config = Config(app_path='app.py', app_factory_name='missing')
    with pytest.raises(AiohttpDevConfigError) as excinfo:
        config.import_app_factory()
    assert excinfo.value.args[0] == 'Module "app.py" does not define a "missing" attribute/class'


@if_boxed
async def test_no_loop_coroutine(tmpworkdir):
    mktree(tmpworkdir, {
        'app.py': """\
from aiohttp import web

async def hello(request):
    return web.Response(text='<h1>hello world</h1>', content_type='text/html')

async def app_factory():
    a = web.Application()
    a.router.add_get('/', hello)
    return a
"""
    })
    config = Config(app_path='app.py')
    app = await config.load_app()
    assert isinstance(app, web.Application)


@if_boxed
async def test_not_app(tmpworkdir):
    mktree(tmpworkdir, {
        'app.py': """\
def app_factory():
    return 123
"""
    })
    config = Config(app_path='app.py')
    with pytest.raises(AiohttpDevConfigError):
        await config.load_app()
