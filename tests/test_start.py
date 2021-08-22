import platform
import sys

import aiohttp
import pytest
from pytest_toolbox import mktree

from aiohttp_devtools.exceptions import AiohttpDevConfigError
from aiohttp_devtools.runserver.config import Config
from aiohttp_devtools.runserver.serve import modify_main_app
from aiohttp_devtools.start import StartProject

IS_WINDOWS = platform.system() == 'Windows'


def test_start_simple(tmpdir, smart_caplog):
    StartProject(path=str(tmpdir), name='foobar')
    assert {p.basename for p in tmpdir.listdir()} == {
        'app',
        'requirements.txt',
        'README.md',
        'static',
        '__init__.py',
    }
    if IS_WINDOWS:
        log_path = r'"C:\Users\appveyor\AppData\Local\Temp\..."'
        log_normalizers = (r'"C:\\Users\\appveyor\\AppData\\Local\\Temp\\.*?"', log_path.replace('\\', r'\\'))
    else:
        log_path = '"/tmp/..."'
        log_normalizers = ('"/tmp/.*?"', log_path)
    assert """\
adev.main INFO: Starting new aiohttp project "foobar" at {}
adev.main INFO: project created, 14 files generated\n""".format(log_path) == smart_caplog(log_normalizers)


@pytest.mark.skipif(sys.version_info < (3, 6), reason='start app requires python >= 3.6')
@pytest.mark.boxed
async def test_start_run(tmpdir, loop, aiohttp_client, smart_caplog):
    StartProject(path=str(tmpdir.join('the-path')), name='foobar')
    assert {p.basename for p in tmpdir.listdir()} == {'the-path'}
    assert {p.basename for p in tmpdir.join('the-path').listdir()} == {
        'app',
        'requirements.txt',
        'README.md',
        'static',
        '__init__.py',
    }
    assert """\
adev.main INFO: Starting new aiohttp project "foobar" at "/<tmpdir>/the-path"
adev.main INFO: project created, 14 files generated\n""" == smart_caplog.log.replace(str(tmpdir), '/<tmpdir>')
    config = Config(app_path='the-path/app/', root_path=str(tmpdir), static_path='.')
    app_factory = config.import_app_factory()
    app = await app_factory()
    modify_main_app(app, config)
    assert isinstance(app, aiohttp.web.Application)

    cli = await aiohttp_client(app)
    r = await cli.get('/')
    assert r.status == 200
    text = await r.text()
    assert "Success! you&#39;ve setup a basic aiohttp app." in text


def test_conflicting_file(tmpdir):
    mktree(tmpdir, {
        'README.md': '...',
    })
    with pytest.raises(AiohttpDevConfigError) as excinfo:
        StartProject(path=str(tmpdir), name='foobar')
    assert excinfo.value.args[0].endswith('has files/directories which would conflict with the new project: README.md')
