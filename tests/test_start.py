import itertools

import pytest
from flake8.api import legacy as flake8

from aiohttp_devtools.exceptions import AiohttpDevConfigError
from aiohttp_devtools.start import StartProject
from aiohttp_devtools.start.main import Options
from tests.conftest import mktree


def test_start_simple(tmpdir, caplog):
    StartProject(path=str(tmpdir), name='foobar')
    assert {p.basename for p in tmpdir.listdir()} == {
        'app',
        'Makefile',
        'requirements.txt',
        'README.md',
        'settings.yml',
        'setup.cfg',
        'static',
        'tests',
    }
    assert """\
adev.main: Starting new aiohttp project "foobar" at "/tmp/..."
adev.main: config:
    template_engine: jinja2
    session: secure
    database: postgres-sqlalchemy
    example: message-board
adev.main: project created, 17 files generated\n""" == caplog(('"/tmp/.*?"', '"/tmp/..."'))


def test_start_other_dir(tmpworkdir, caplog):
    StartProject(path=str(tmpworkdir.join('the-path')), name='foobar', database=Options.NONE)
    assert {p.basename for p in tmpworkdir.listdir()} == {'the-path'}
    assert {p.basename for p in tmpworkdir.join('the-path').listdir()} == {
        'app',
        'Makefile',
        'requirements.txt',
        'README.md',
        'settings.yml',
        'setup.cfg',
        'static',
        'tests',
    }
    assert """\
adev.main: Starting new aiohttp project "foobar" at "the-path"
adev.main: config:
    template_engine: jinja2
    session: secure
    database: none
    example: message-board
adev.main: project created, 15 files generated\n""" == caplog.log


def test_conflicting_file(tmpdir):
    mktree(tmpdir, {
        'Makefile': '...',
    })
    with pytest.raises(AiohttpDevConfigError) as excinfo:
        StartProject(path=str(tmpdir), name='foobar')
    assert excinfo.value.args[0] == ('The path you supplied already has files/directories which would '
                                     'conflict with the new project: Makefile')


@pytest.mark.parametrize('template_engine,session,database,example', itertools.product(
    Options.TEMPLATE_ENG_CHOICES,
    Options.SESSION_CHOICES,
    Options.DB_CHOICES,
    Options.EXAMPLE_CHOICES,
))
def test_all_options(tmpdir, template_engine, session, database, example):
    StartProject(
        path=str(tmpdir),
        name='foobar',
        template_engine=template_engine,
        session=session,
        database=database,
        example=example,
    )
    style_guide = flake8.get_style_guide()
    report = style_guide.check_files([str(tmpdir)])
    assert report.total_errors == 0
