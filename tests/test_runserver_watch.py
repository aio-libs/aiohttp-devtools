from platform import system as get_os_family
from unittest.mock import MagicMock, call

from aiohttp.web import Application

from aiohttp_devtools.runserver.watch import AppTask, LiveReloadTask

from .conftest import create_future


non_windows_test = pytest.mark.skipif(
    get_os_family() == 'Windows',
    reason='This only works under UNIX-based OS and gets stuck under Windows',
)


def create_awatch_mock(*results):
    results = results or [{('x', '/path/to/file')}]

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


async def test_single_file_change(loop, mocker):
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = create_awatch_mock()
    mock_src_reload = mocker.patch('aiohttp_devtools.runserver.watch.src_reload', return_value=create_future())

    app_task = AppTask(MagicMock(), loop)
    app_task._start_dev_server = MagicMock()
    app_task._stop_dev_server = MagicMock()
    app_task._app = MagicMock()
    await app_task._run()
    mock_src_reload.assert_called_once_with(app_task._app, '/path/to/file')
    assert app_task._start_dev_server.call_count == 1
    assert app_task._stop_dev_server.called is False
    await app_task._session.close()


async def test_multiple_file_change(loop, mocker):
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = create_awatch_mock({('x', '/path/to/file'), ('x', '/path/to/file2')})
    mock_src_reload = mocker.patch('aiohttp_devtools.runserver.watch.src_reload', return_value=create_future())
    app_task = AppTask(MagicMock(), loop)
    app_task._start_dev_server = MagicMock()
    app_task._stop_dev_server = MagicMock()

    app_task._app = MagicMock()
    await app_task._run()
    mock_src_reload.assert_called_once_with(app_task._app)
    assert app_task._start_dev_server.call_count == 1
    await app_task._session.close()


@non_windows_test
async def test_python_no_server(loop, mocker):
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = create_awatch_mock({('x', '/path/to/file.py')})

    config = MagicMock()
    config.main_port = 8000
    app_task = AppTask(config, loop)
    app_task._start_dev_server = MagicMock()
    app_task._stop_dev_server = MagicMock()
    app_task._app = MagicMock()
    await app_task._run()
    assert app_task._app.src_reload.called is False
    assert app_task._start_dev_server.called
    assert app_task._stop_dev_server.called
    await app_task._session.close()


async def test_reload_server_running(loop, test_client, mocker):
    app = Application()
    app['websockets'] = [None]
    mock_src_reload = mocker.patch('aiohttp_devtools.runserver.watch.src_reload', return_value=create_future())
    cli = await test_client(app)
    config = MagicMock()
    config.main_port = cli.server.port

    app_task = AppTask(config, loop)
    app_task._app = app
    await app_task._src_reload_when_live(2)
    mock_src_reload.assert_called_once_with(app)
    await app_task._session.close()


async def test_livereload_task_single(loop, mocker):
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = create_awatch_mock()
    mock_src_reload = mocker.patch('aiohttp_devtools.runserver.watch.src_reload', return_value=create_future())

    task = LiveReloadTask('x', loop)
    task._app = MagicMock()
    await task._run()
    mock_src_reload.assert_called_once_with(task._app, '/path/to/file')


async def test_livereload_task_multiple(loop, mocker):
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = create_awatch_mock({('x', '/path/to/file'), ('x', '/path/to/file2')})
    mock_src_reload = mocker.patch('aiohttp_devtools.runserver.watch.src_reload', return_value=create_future())

    task = LiveReloadTask('x', loop)
    task._app = MagicMock()
    await task._run()
    mock_src_reload.assert_called_once_with(task._app)


class FakeProcess:
    def __init__(self, is_alive=True, exitcode=1, pid=123):
        self._is_alive = is_alive
        self.exitcode = exitcode
        self.pid = pid

    def is_alive(self):
        return self._is_alive

    def join(self, wait):
        pass


def test_stop_process_dead(smart_caplog, mocker):
    mock_kill = mocker.patch('aiohttp_devtools.runserver.watch.os.kill')
    mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    app_task = AppTask(MagicMock(), MagicMock())
    app_task._process = MagicMock()
    app_task._process.is_alive = MagicMock(return_value=False)
    app_task._process.exitcode = 123
    app_task._stop_dev_server()
    assert 'server process already dead, exit code: 123' in smart_caplog
    assert mock_kill.called is False


def test_stop_process_clean(mocker):
    mock_kill = mocker.patch('aiohttp_devtools.runserver.watch.os.kill')
    mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    app_task = AppTask(MagicMock(), MagicMock())
    app_task._process = MagicMock()
    app_task._process.is_alive = MagicMock(return_value=True)
    app_task._process.pid = 321
    app_task._process.exitcode = 123
    app_task._stop_dev_server()
    assert mock_kill.called_once_with(321, 2)


def test_stop_process_dirty(mocker):
    mock_kill = mocker.patch('aiohttp_devtools.runserver.watch.os.kill')
    mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    app_task = AppTask(MagicMock(), MagicMock())
    app_task._process = MagicMock()
    app_task._process.is_alive = MagicMock(return_value=True)
    app_task._process.pid = 321
    app_task._process.exitcode = None
    app_task._stop_dev_server()
    assert mock_kill.call_args_list == [
        call(321, 2),
        call(321, 9),
    ]
