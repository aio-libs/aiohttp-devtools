from datetime import datetime
from unittest.mock import MagicMock

from aiohttp_devtools.runserver.serve import serve_main_app
from aiohttp_devtools.runserver.watch import AllCodeEventHandler, LiveReloadEventHandler, PyCodeEventHandler


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


def test_pycode(mocker):
    mock_process = mocker.patch('aiohttp_devtools.runserver.watch.Process')
    mock_os_kill = mocker.patch('aiohttp_devtools.runserver.watch.os.kill')
    app = MagicMock()
    config = MagicMock()
    PyCodeEventHandler(app, config)
    mock_process.assert_called_once_with(target=serve_main_app, args=(config,))
    assert mock_os_kill.call_count == 0


def test_pycode_event(mocker):
    mock_process = mocker.patch('aiohttp_devtools.runserver.watch.Process')
    mock_process.pid = 123
    mock_os_kill = mocker.patch('aiohttp_devtools.runserver.watch.os.kill')
    app = MagicMock()
    config = MagicMock()

    eh = PyCodeEventHandler(app, config)
    eh._change_dt = datetime(2017, 1, 1)
    eh.dispatch(Event(src_path='foo.py'))
    assert mock_process.call_count == 2
    assert mock_os_kill.call_count == 1
