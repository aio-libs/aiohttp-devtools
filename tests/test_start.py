import itertools
import os
import platform
import subprocess

import aiohttp
import pytest
from flake8.api import legacy as flake8
from pytest_toolbox import mktree

from aiohttp_devtools.exceptions import AiohttpDevConfigError
from aiohttp_devtools.runserver.config import Config
from aiohttp_devtools.runserver.serve import modify_main_app
from aiohttp_devtools.start import DatabaseChoice, ExampleChoice, SessionChoices, StartProject, TemplateChoice
from aiohttp_devtools.start.main import enum_choices

from .conftest import get_if_boxed, get_slow

slow = get_slow(pytest)
if_boxed = get_if_boxed(pytest)


IS_WINDOWS = platform.system() == 'Windows'


def test_start_simple(tmpdir, smart_caplog):
    StartProject(path=str(tmpdir), name='foobar')
    assert {p.basename for p in tmpdir.listdir()} == {
        'app',
        'Makefile',
        'requirements.txt',
        'README.md',
        'activate.settings.sh',
        'setup.cfg',
        'static',
        'tests',
    }
    if IS_WINDOWS:
        log_path = r'"C:\Users\\appveyor\AppData\Local\Temp\..."'
        log_normalizers = (r'"C:\\Users\\appveyor\\AppData\\Local\\Temp\\.*?"', log_path)
    else:
        log_path = '"/tmp/..."'
        log_normalizers = ('"/tmp/.*?"', log_path)
    assert """\
adev.main INFO: Starting new aiohttp project "foobar" at {}
adev.main INFO: config:
    template_engine: jinja
    session: secure
    database: pg-sqlalchemy
    example: message-board
adev.main INFO: project created, 18 files generated\n""".format(log_path) == smart_caplog(log_normalizers)


@if_boxed
async def test_start_other_dir(tmpdir, loop, test_client, smart_caplog):
    StartProject(path=str(tmpdir.join('the-path')), name='foobar', database=DatabaseChoice.NONE)
    assert {p.basename for p in tmpdir.listdir()} == {'the-path'}
    assert {p.basename for p in tmpdir.join('the-path').listdir()} == {
        'app',
        'Makefile',
        'requirements.txt',
        'README.md',
        'activate.settings.sh',
        'setup.cfg',
        'static',
        'tests',
    }
    assert """\
adev.main INFO: Starting new aiohttp project "foobar" at "/<tmpdir>/the-path"
adev.main INFO: config:
    template_engine: jinja
    session: secure
    database: none
    example: message-board
adev.main INFO: project created, 16 files generated\n""" == smart_caplog.log.replace(str(tmpdir), '/<tmpdir>')
    config = Config(app_path='the-path/app/', root_path=str(tmpdir), static_path='.')
    app_factory = config.import_app_factory()
    app = app_factory()
    modify_main_app(app, config)
    assert isinstance(app, aiohttp.web.Application)

    cli = await test_client(app)
    r = await cli.get('/')
    assert r.status == 200
    text = await r.text()
    assert "Success! you&#39;ve setup a basic aiohttp app." in text


def test_conflicting_file(tmpdir):
    mktree(tmpdir, {
        'Makefile': '...',
    })
    with pytest.raises(AiohttpDevConfigError) as excinfo:
        StartProject(path=str(tmpdir), name='foobar')
    assert excinfo.value.args[0].endswith('has files/directories which would conflict with the new project: Makefile')


@if_boxed
@slow
@pytest.mark.parametrize('template_engine,session,database,example', itertools.product(
    enum_choices(TemplateChoice),
    enum_choices(SessionChoices),
    enum_choices(DatabaseChoice),
    enum_choices(ExampleChoice),
))
async def test_all_options(tmpdir, test_client, loop, template_engine, session, database, example):
    StartProject(
        path=str(tmpdir),
        name='foobar',
        template_engine=template_engine,
        session=session,
        database=database,
        example=example,
    )
    assert 'app' in {p.basename for p in tmpdir.listdir()}
    style_guide = flake8.get_style_guide()
    report = style_guide.check_files([str(tmpdir)])
    assert report.total_errors == 0
    if database != 'none':
        return
    config = Config(app_path='app/main.py', root_path=str(tmpdir), static_path='.')

    app_factory = config.import_app_factory()
    app = app_factory()
    modify_main_app(app, config)
    cli = await test_client(app)
    r = await cli.get('/')
    assert r.status == 200
    text = await r.text()
    assert '<title>foobar</title>' in text


@if_boxed
@slow
async def test_db_creation(tmpdir, test_client, loop):
    StartProject(
        path=str(tmpdir),
        name='foobar postgres test',
        template_engine=TemplateChoice.JINJA,
        session=SessionChoices.NONE,
        database=DatabaseChoice.PG_SA,
        example=ExampleChoice.MESSAGE_BOARD,
    )
    assert 'app' in {p.basename for p in tmpdir.listdir()}
    style_guide = flake8.get_style_guide()
    report = style_guide.check_files([str(tmpdir)])
    assert report.total_errors == 0
    db_password = os.getenv('APP_DB_PASSWORD', '')
    env = {
        'APP_DB_PASSWORD': db_password,
        'PATH': os.getenv('PATH', ''),
    }
    p = subprocess.run(['make', 'reset-database'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       cwd=str(tmpdir), env=env, universal_newlines=True)
    assert p.returncode == 0, p.stdout
    assert 'creating database "foobar"...'
    assert 'creating tables from model definition...'

    os.environ['APP_DB_PASSWORD'] = db_password
    config = Config(app_path='app/main.py', root_path=str(tmpdir), static_path='.')

    app_factory = config.import_app_factory()
    app = app_factory()
    modify_main_app(app, config)
    cli = await test_client(app)
    r = await cli.get('/')
    assert r.status == 200
    text = await r.text()
    assert '<title>foobar postgres test</title>' in text
