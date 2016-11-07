import pytest

from aiohttp_devtools.exceptions import AiohttpDevConfigError
from aiohttp_devtools.runserver.config import Config

from .conftest import SIMPLE_APP, mktree

async def test_load_simple_app(tmpworkdir):
    mktree(tmpworkdir, SIMPLE_APP)
    Config(app_path='app.py')

async def test_create_app_wrong_name(tmpworkdir):
    mktree(tmpworkdir, SIMPLE_APP)
    with pytest.raises(AiohttpDevConfigError) as excinfo:
        Config(app_path='app.py', app_factory='missing')
    assert excinfo.value.args[0] == 'Module "app.py" does not define a "missing" attribute/class'


async def test_yml_file(tmpdir):
    files = dict(SIMPLE_APP)
    files['settings.yml'] = """\
dev:
  py_file: app.py"""
    mktree(tmpdir, files)
    Config(app_path=str(tmpdir))


invalid_apps = [
    (
        {
            'foo': 'bar',
        },
        'unable to find a recognised default file ("settings.yml", "app.py" or "main.py") in the directory "."'
    ),
    (
        {
            'settings.yml': 'b: 4'
         },
        'Invalid settings file, {tmpworkdir}/settings.yml:1: dev: is required'
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
        'app_factory "create_app" is not callable'
    ),
    (
        {
            'app.py': """\
from trafaret_config import ConfigError
def app_factory(loop):
    raise ConfigError(['error'])""",
        },
        'app factory "app_factory" caused ConfigError: error'
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


@pytest.mark.parametrize('files,exc', invalid_apps, ids=['%s...' % v[1][:40] for v in invalid_apps])
def test_all_options(tmpworkdir, files, exc):
    mktree(tmpworkdir, files)
    with pytest.raises(AiohttpDevConfigError) as excinfo:
        Config(app_path='.').check()
    assert exc.format(tmpworkdir=tmpworkdir) == excinfo.value.args[0]
