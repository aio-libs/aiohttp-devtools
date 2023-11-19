import asyncio
from functools import partial
from typing import Set, Tuple
from unittest.mock import MagicMock, call

from aiohttp import ClientSession
from aiohttp.web import Application, WebSocketResponse

from aiohttp_devtools.runserver.serve import STATIC_PATH, WS
from aiohttp_devtools.runserver.watch import AppTask, LiveReloadTask

from .conftest import create_future


def create_awatch_mock(*results_):
    results = results_ or [{("x", "/path/to/file")}]

    class awatch_mock:
        def __init__(self, path, **kwargs):
            self._result = iter(results)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._result)
            except StopIteration:
                raise StopAsyncIteration
    return awatch_mock


async def test_single_file_change(event_loop, mocker):
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = create_awatch_mock()
    mock_src_reload = mocker.patch('aiohttp_devtools.runserver.watch.src_reload', return_value=create_future())

    app = MagicMock()
    app_task = AppTask(app)
    start_mock = mocker.patch.object(app_task, "_start_dev_server", autospec=True)
    stop_mock = mocker.patch.object(app_task, "_stop_dev_server", autospec=True)
    app = MagicMock()
    await app_task.start(app)
    d = {STATIC_PATH: "/path/to/"}
    app.__getitem__.side_effect = d.__getitem__
    assert app_task._task is not None
    await app_task._task
    mock_src_reload.assert_called_once_with(app, '/path/to/file')
    assert start_mock.call_count == 1
    assert stop_mock.called is False
    assert app_task._session is not None
    await app_task._session.close()


async def test_multiple_file_change(event_loop, mocker):
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = create_awatch_mock({('x', '/path/to/file'), ('x', '/path/to/file2')})
    mock_src_reload = mocker.patch('aiohttp_devtools.runserver.watch.src_reload', return_value=create_future())
    app_task = AppTask(MagicMock())
    start_mock = mocker.patch.object(app_task, "_start_dev_server", autospec=True)
    mocker.patch.object(app_task, "_stop_dev_server", autospec=True)

    app = MagicMock()
    await app_task.start(app)
    assert app_task._task is not None
    await app_task._task
    mock_src_reload.assert_called_once_with(app)
    assert start_mock.call_count == 1
    assert app_task._session is not None
    await app_task._session.close()


async def test_python_no_server(event_loop, mocker):
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = create_awatch_mock({('x', '/path/to/file.py')})

    config = MagicMock()
    config.main_port = 8000
    app_task = AppTask(config)
    start_mock = mocker.patch.object(app_task, "_start_dev_server", autospec=True)
    stop_mock = mocker.patch.object(app_task, "_stop_dev_server", autospec=True)
    mocker.patch.object(app_task, "_run", partial(app_task._run, live_checks=2))
    app = Application()
    app[STATIC_PATH] = "/path/to/"
    app.src_reload = MagicMock()
    mock_ws = MagicMock()
    f: asyncio.Future[int] = asyncio.Future()
    f.set_result(1)
    mock_ws.send_str = MagicMock(return_value=f)
    app[WS] = set(((mock_ws, "/"),))  # type: ignore[misc]
    await app_task.start(app)
    assert app_task._task is not None
    await app_task._task
    assert config.src_reload.called is False
    assert start_mock.called
    assert stop_mock.called
    assert app_task._session is not None
    await app_task._session.close()


async def test_reload_server_running(event_loop, aiohttp_client, mocker):
    app = Application()
    ws: Set[Tuple[WebSocketResponse, str]] = set(((MagicMock(), "/foo"),))
    app[WS] = ws
    mock_src_reload = mocker.patch('aiohttp_devtools.runserver.watch.src_reload', return_value=create_future())
    cli = await aiohttp_client(app)
    config = MagicMock()
    config.main_port = cli.server.port

    app_task = AppTask(config)
    app_task._app = app
    app_task._session = ClientSession()  # match behaviour of _run()
    await app_task._src_reload_when_live(2)
    mock_src_reload.assert_called_once_with(app)
    await app_task._session.close()


async def test_livereload_task_single(event_loop, mocker):
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = create_awatch_mock()
    mock_src_reload = mocker.patch('aiohttp_devtools.runserver.watch.src_reload', return_value=create_future())

    task = LiveReloadTask('x')
    app = MagicMock()
    await task.start(app)
    assert task._task is not None
    await task._task
    mock_src_reload.assert_called_once_with(app, '/path/to/file')


async def test_livereload_task_multiple(event_loop, mocker):
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = create_awatch_mock({('x', '/path/to/file'), ('x', '/path/to/file2')})
    mock_src_reload = mocker.patch('aiohttp_devtools.runserver.watch.src_reload', return_value=create_future())

    task = LiveReloadTask('x')
    app = MagicMock()
    await task.start(app)
    assert task._task is not None
    await task._task
    mock_src_reload.assert_called_once_with(app)


class FakeProcess:
    def __init__(self, is_alive=True, exitcode=1, pid=123):
        self._is_alive = is_alive
        self.exitcode = exitcode
        self.pid = pid

    def is_alive(self):
        return self._is_alive

    def join(self, wait):
        pass


async def test_stop_process_dead(smart_caplog, mocker):
    mock_kill = mocker.patch('aiohttp_devtools.runserver.watch.os.kill')
    mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocker.patch('asyncio.Event')
    app_task = AppTask(MagicMock())
    app_task._process = MagicMock()
    app_task._process.is_alive = MagicMock(return_value=False)
    app_task._process.exitcode = 123
    await app_task._stop_dev_server()
    assert 'server process already dead, exit code: 123' in smart_caplog
    assert mock_kill.called is False


async def test_stop_process_clean(mocker):
    mock_kill = mocker.patch('aiohttp_devtools.runserver.watch.os.kill')
    mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocker.patch('asyncio.Event')
    app_task = AppTask(MagicMock())
    app_task._process = MagicMock()
    app_task._process.is_alive = MagicMock(return_value=True)
    app_task._process.pid = 321
    app_task._process.exitcode = 123
    await app_task._stop_dev_server()
    assert mock_kill.called_once_with(321, 2)


async def test_stop_process_dirty(mocker):
    mock_kill = mocker.patch('aiohttp_devtools.runserver.watch.os.kill')
    mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    app_task = AppTask(MagicMock())
    process_mock = MagicMock()
    app_task._process = process_mock
    process_mock.is_alive = MagicMock(return_value=True)
    process_mock.pid = 321
    process_mock.exitcode = None
    await app_task._stop_dev_server()
    assert mock_kill.call_args_list == [call(321, 2)]
    assert process_mock.kill.called_once()
