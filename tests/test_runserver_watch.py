from unittest.mock import MagicMock

from aiohttp.web import Application

from aiohttp_devtools.runserver.watch import AppTask, LiveReloadTask

from .conftest import create_future


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


async def fake_start_main_app(config):
    class mock_runner:
        async def cleanup(self):
            pass
    return mock_runner()


async def test_single_file_change(loop, mocker):
    mocker.patch('aiohttp_devtools.runserver.watch.awatch', side_effect=create_awatch_mock())
    mocked_start_main_app = mocker.patch('aiohttp_devtools.runserver.watch.start_main_app')
    mocked_start_main_app.side_effect = fake_start_main_app
    mock_src_reload = mocker.patch('aiohttp_devtools.runserver.watch.src_reload', return_value=create_future())

    app_task = AppTask(MagicMock(), loop)
    app_task._app = MagicMock()
    await app_task._run()
    mock_src_reload.assert_called_once_with(app_task._app, '/path/to/file')
    assert mocked_start_main_app.call_count == 1
    await app_task._session.close()


async def test_multiple_file_change(loop, mocker):
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = create_awatch_mock({('x', '/path/to/file'), ('x', '/path/to/file2')})
    mocked_start_main_app = mocker.patch('aiohttp_devtools.runserver.watch.start_main_app')
    mocked_start_main_app.side_effect = fake_start_main_app
    mock_src_reload = mocker.patch('aiohttp_devtools.runserver.watch.src_reload', return_value=create_future())

    app_task = AppTask(MagicMock(), loop)
    app_task._app = MagicMock()
    await app_task._run()
    mock_src_reload.assert_called_once_with(app_task._app)
    assert mocked_start_main_app.call_count == 1
    await app_task._session.close()


async def test_python_no_server(loop, mocker):
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = create_awatch_mock({('x', '/path/to/file.py')})
    mocked_start_main_app = mocker.patch('aiohttp_devtools.runserver.watch.start_main_app')
    mocked_start_main_app.side_effect = fake_start_main_app
    mock_src_reload = mocker.patch('aiohttp_devtools.runserver.watch.src_reload', return_value=create_future())

    config = MagicMock()
    config.main_port = 8000
    app_task = AppTask(config, loop)
    app_task._app = MagicMock()
    await app_task._run()
    assert mock_src_reload.call_count == 0
    assert mocked_start_main_app.call_count == 2
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
    mocker.patch('aiohttp_devtools.runserver.watch.awatch', side_effect=create_awatch_mock())
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
