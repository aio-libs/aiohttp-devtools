import signal
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from aiohttp.web import Application

from aiohttp_devtools.runserver.serve import serve_main_app
from aiohttp_devtools.runserver.watch import AllCodeEventHandler, LiveReloadEventHandler, PyCodeEventHandler
from tests.conftest import get_if_boxed

if_boxed = get_if_boxed(pytest)


class Event:
    def __init__(self, src_path='foo', dest_path='bar', is_directory=False):
        self.is_directory = is_directory
        self.src_path = src_path
        self.dest_path = dest_path


def test_simple():
    app = MagicMock()
    eh = AllCodeEventHandler(app)
    eh._change_dt = datetime(2017, 1, 1)
    eh.dispatch(Event(src_path='foo.jinja'))
    app.src_reload.assert_called_once_with()


def test_debounce():
    app = MagicMock()
    eh = AllCodeEventHandler(app)
    eh._change_dt = datetime(2017, 1, 1)
    eh.dispatch(Event(src_path='foo.jinja'))
    eh.dispatch(Event(src_path='foo.html'))
    assert app.src_reload.call_count == 1


def test_not_debounce():
    app = MagicMock()
    eh = AllCodeEventHandler(app)
    eh._change_dt = datetime(2017, 1, 1)
    eh.dispatch(Event(src_path='foo.jinja'))
    eh._change_dt = datetime(2017, 1, 1)
    eh.dispatch(Event(src_path='foo.html'))
    assert app.src_reload.call_count == 2


def test_directory():
    app = MagicMock()
    eh = AllCodeEventHandler(app)
    eh._change_dt = datetime(2017, 1, 1)
    eh.dispatch(Event(src_path='foo.jinja', is_directory=True))
    assert app.src_reload.call_count == 0


def test_wrong_ext():
    app = MagicMock()
    eh = AllCodeEventHandler(app)
    eh._change_dt = datetime(2017, 1, 1)
    eh.dispatch(Event(src_path='foo.jinja_not'))
    assert app.src_reload.call_count == 0


def test_move():
    app = MagicMock()
    eh = AllCodeEventHandler(app)
    eh._change_dt = datetime(2017, 1, 1)
    eh.dispatch(Event(src_path='foo.jinja_not', dest_path='foo.jinja'))
    assert app.src_reload.call_count == 1


def test_move_jet_brains():
    app = MagicMock()
    eh = AllCodeEventHandler(app)
    eh._change_dt = datetime(2017, 1, 1)
    eh.dispatch(Event(src_path='foo.___jb_bak___', dest_path='foo.jinja'))
    assert app.src_reload.call_count == 0


def test_no_dest():
    app = MagicMock()
    eh = AllCodeEventHandler(app)
    eh._change_dt = datetime(2017, 1, 1)

    class _Event:
        is_directory = False
        src_path = 'foobar.jinja'

    eh.dispatch(_Event())
    assert app.src_reload.call_count == 1


def test_no_src():
    app = MagicMock()
    eh = AllCodeEventHandler(app)
    eh._change_dt = datetime(2017, 1, 1)

    eh.dispatch(Event(src_path=None, dest_path='foo.html'))
    assert app.src_reload.call_count == 1


def test_livereload():
    app = MagicMock()
    eh = LiveReloadEventHandler(app)
    eh._change_dt = datetime(2017, 1, 1)
    eh.dispatch(Event(src_path='foo.jinja'))
    app.src_reload.assert_called_once_with('foo.jinja')


def test_pycode(mocker, caplog):
    mock_process = mocker.patch('aiohttp_devtools.runserver.watch.Process')
    mock_os_kill = mocker.patch('aiohttp_devtools.runserver.watch.os.kill')
    app = MagicMock()
    config = MagicMock()
    PyCodeEventHandler(app, config)
    mock_process.assert_called_once_with(target=serve_main_app, args=(config,))
    assert mock_os_kill.call_count == 0
    assert 'adev.server.dft INFO: Starting dev server at' in caplog
    assert 'adev.server.dft INFO: Restarting dev server at' not in caplog


def test_pycode_event(mocker, caplog):
    mock_process = mocker.patch('aiohttp_devtools.runserver.watch.Process')
    mock_os_kill = mocker.patch('aiohttp_devtools.runserver.watch.os.kill')
    app = MagicMock()
    config = MagicMock()

    eh = PyCodeEventHandler(app, config)
    eh._change_dt = datetime(2017, 1, 1)
    eh.dispatch(Event(src_path='foo.py'))
    assert mock_process.call_count == 2
    assert mock_os_kill.call_count == 1
    assert 'adev.server.dft INFO: Starting dev server at' in caplog
    assert 'adev.server.dft INFO: Restarting dev server at' in caplog


def test_pycode_event_dead_process(mocker):
    mock_process = mocker.patch('aiohttp_devtools.runserver.watch.Process')
    process = MagicMock()
    process.is_alive = MagicMock(return_value=False)
    mock_process.return_value = process
    mock_os_kill = mocker.patch('aiohttp_devtools.runserver.watch.os.kill')
    app = MagicMock()
    config = MagicMock()

    eh = PyCodeEventHandler(app, config)
    eh._change_dt = datetime(2017, 1, 1)
    eh.dispatch(Event(src_path='foo.py'))
    assert mock_process.call_count == 2
    assert mock_os_kill.call_count == 0


def test_pycode_event_process_not_ending(mocker):
    mock_process = mocker.patch('aiohttp_devtools.runserver.watch.Process')
    process = MagicMock()
    process.pid = 123
    process.exitcode = None
    mock_process.return_value = process
    mock_os_kill = mocker.patch('aiohttp_devtools.runserver.watch.os.kill')
    app = MagicMock()
    config = MagicMock()

    eh = PyCodeEventHandler(app, config)
    eh._change_dt = datetime(2017, 1, 1)
    eh.dispatch(Event(src_path='foo.py'))
    assert mock_process.call_count == 2
    assert mock_os_kill.call_args_list == [
        ((123, signal.SIGINT),),
        ((123, signal.SIGKILL),),
    ]


@if_boxed
async def test_pycode_src_reload_when_live_timeout(caplog, loop, mocker, unused_port):
    caplog.set_level(10)
    mock_process = mocker.patch('aiohttp_devtools.runserver.watch.Process')
    process = MagicMock()
    process.pid = 123
    process.exitcode = None
    mock_process.return_value = process

    app = MagicMock()
    app.loop = loop
    config = MagicMock()
    config.main_port = unused_port()

    eh = PyCodeEventHandler(app, config)
    r = await eh.src_reload_when_live(2)
    assert r is None
    assert 'adev.server.dft DEBUG: try 1 | OSError 111 app not running' in caplog
    assert app.src_reload.call_count == 0


async def test_pycode_src_reload_when_live_running(caplog, loop, mocker, test_client):
    caplog.set_level(10)
    mock_process = mocker.patch('aiohttp_devtools.runserver.watch.Process')
    process = MagicMock()
    process.pid = 123
    process.exitcode = None
    mock_process.return_value = process

    app = Application(loop=loop)
    app['websockets'] = [None]
    app.src_reload = MagicMock(return_value=0)
    cli = await test_client(app)
    config = MagicMock()
    config.main_port = cli.server.port

    eh = PyCodeEventHandler(app, config)
    r = await eh.src_reload_when_live(2)
    assert r == 0
    assert app.src_reload.call_count == 1


async def test_pycode_src_reload_when_live_no_webs(caplog, loop, mocker, test_client):
    caplog.set_level(10)
    mock_process = mocker.patch('aiohttp_devtools.runserver.watch.Process')
    process = MagicMock()
    process.pid = 123
    process.exitcode = None
    mock_process.return_value = process

    app = Application(loop=loop)
    app['websockets'] = []
    app.src_reload = MagicMock()
    cli = await test_client(app)
    config = MagicMock()
    config.main_port = cli.server.port

    eh = PyCodeEventHandler(app, config)
    r = await eh.src_reload_when_live(2)
    assert r is None
    assert not app.src_reload.called
