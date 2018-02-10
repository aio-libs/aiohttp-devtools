import pytest
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


invalid_apps = [
    (
        {
            'foo': 'bar',
        },
        'unable to find a recognised default file ("app.py" or "main.py") in the directory "."'
    ),
    (
        {
            'app.py': """\
def not_a_default_name(loop):
    pass"""
         },
        'No name supplied and no default app factory found in app.py'
    ),
    (
        {
            'app.py': 'create_app = 4',
        },
        'app_factory "create_app" is not callable or an instance of aiohttp.web.Application'
    ),
    (
         {
            'app.py': """\
def app_factory(loop):
    return 43""",
         },
         'app factory "app_factory" returned "int" not an aiohttp.web.Application'
    )
]
