from unittest.mock import MagicMock, call

from aiohttp.web import Application

from aiohttp_devtools.runserver.watch import AppTask, LiveReloadTask


def create_awatch_mock(*results):
    results = results or [{('x', '/path/to/file')}]

    class awatch_mock:
        def __init__(self, path):
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

    app_task = AppTask(MagicMock(), loop)
    app_task._start_process = MagicMock()
    app_task.stop_process = MagicMock()
    app_task._app = MagicMock()
    await app_task._run()
    app_task._app.src_reload.assert_called_once_with('/path/to/file')
    assert app_task._start_process.call_count == 1
    assert app_task.stop_process.called is False
    app_task._session.close()


async def test_multiple_file_change(loop, mocker):
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = create_awatch_mock({('x', '/path/to/file'), ('x', '/path/to/file2')})
    app_task = AppTask(MagicMock(), loop)
    app_task._start_process = MagicMock()
    app_task.stop_process = MagicMock()

    app_task._app = MagicMock()
    await app_task._run()
    app_task._app.src_reload.assert_called_once_with()
    app_task._session.close()


async def test_python_no_server(loop, mocker):
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = create_awatch_mock({('x', '/path/to/file.py')})

    config = MagicMock()
    config.main_port = 8000
    app_task = AppTask(config, loop)
    app_task._start_process = MagicMock()
    app_task.stop_process = MagicMock()
    app_task._app = MagicMock()
    await app_task._run()
    assert app_task._app.src_reload.called is False
    assert app_task._start_process.called
    assert app_task.stop_process.called
    app_task._session.close()


async def test_reload_server_running(loop, test_client):
    app = Application()
    app['websockets'] = [None]
    app.src_reload = MagicMock()
    cli = await test_client(app)
    config = MagicMock()
    config.main_port = cli.server.port

    app_task = AppTask(config, loop)
    app_task._app = app
    await app_task._src_reload_when_live(2)
    app.src_reload.assert_called_once_with()
    app_task._session.close()


async def test_livereload_task_single(loop, mocker):
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = create_awatch_mock()

    task = LiveReloadTask('x', loop)
    task._app = MagicMock()
    await task._run()
    task._app.src_reload.assert_called_once_with('/path/to/file')


async def test_livereload_task_multiple(loop, mocker):
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = create_awatch_mock({('x', '/path/to/file'), ('x', '/path/to/file2')})

    task = LiveReloadTask('x', loop)
    task._app = MagicMock()
    await task._run()
    task._app.src_reload.assert_called_once_with()


class FakeProcess:
    def __init__(self, is_alive=True, exitcode=1, pid=123):
        self._is_alive = is_alive
        self.exitcode = exitcode
        self.pid = pid

    def is_alive(self):
        return self._is_alive

    def join(self, wait):
        pass


def test_stop_process_dead(caplog, mocker):
    mock_kill = mocker.patch('aiohttp_devtools.runserver.watch.os.kill')
    mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    app_task = AppTask(MagicMock(), MagicMock())
    app_task._process = MagicMock()
    app_task._process.is_alive = MagicMock(return_value=False)
    app_task._process.exitcode = 123
    app_task.stop_process()
    assert 'server process already dead, exit code: 123' in caplog
    assert mock_kill.called is False


def test_stop_process_clean(caplog, mocker):
    mock_kill = mocker.patch('aiohttp_devtools.runserver.watch.os.kill')
    mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    app_task = AppTask(MagicMock(), MagicMock())
    app_task._process = MagicMock()
    app_task._process.is_alive = MagicMock(return_value=True)
    app_task._process.pid = 321
    app_task._process.exitcode = 123
    app_task.stop_process()
    assert mock_kill.called_once_with(321, 2)


def test_stop_process_dirty(caplog, mocker):
    mock_kill = mocker.patch('aiohttp_devtools.runserver.watch.os.kill')
    mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    app_task = AppTask(MagicMock(), MagicMock())
    app_task._process = MagicMock()
    app_task._process.is_alive = MagicMock(return_value=True)
    app_task._process.pid = 321
    app_task._process.exitcode = None
    app_task.stop_process()
    assert mock_kill.call_args_list == [
        call(321, 2),
        call(321, 9),
    ]
