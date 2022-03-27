import pytest
from aiohttp import web
from pytest_toolbox import mktree

from aiohttp_devtools.exceptions import AiohttpDevConfigError
from aiohttp_devtools.runserver.config import Config

from .conftest import SIMPLE_APP, forked


async def test_load_simple_app(tmpworkdir):
    mktree(tmpworkdir, SIMPLE_APP)
    Config(app_path='app.py')


@forked
async def test_create_app_wrong_name(tmpworkdir, event_loop):
    mktree(tmpworkdir, SIMPLE_APP)
    config = Config(app_path='app.py', app_factory_name='missing')
    with pytest.raises(AiohttpDevConfigError) as excinfo:
        config.import_app_factory()
    assert excinfo.value.args[0] == "Module 'app.py' does not define a 'missing' attribute/class"


@forked
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
    app = await config.load_app(config.import_app_factory())
    assert isinstance(app, web.Application)


@forked
async def test_not_app(tmpworkdir):
    mktree(tmpworkdir, {
        'app.py': """\
def app_factory():
    return 123
"""
    })
    config = Config(app_path='app.py')
    with pytest.raises(AiohttpDevConfigError,
                       match=r"'app_factory' returned 'int' not an aiohttp\.web\.Application"):
        await config.load_app(config.import_app_factory())


@forked
async def test_wrong_function_signature(tmpworkdir):
    mktree(tmpworkdir, {
        'app.py': """\
def app_factory(foo):
    return web.Application()
"""
    })
    config = Config(app_path='app.py')
    with pytest.raises(AiohttpDevConfigError,
                       match=r"'app\.py\.app_factory' should not have required arguments"):
        await config.load_app(config.import_app_factory())
