import sys
from unittest.mock import MagicMock

import pytest
from aiohttp.web import Application

from aiohttp_devtools.runserver.watch import AppTask, LiveReloadTask

PY35 = sys.version_info < (3, 6)


@pytest.mark.skipif(PY35, reason='no async generators in python 3.5')
async def test_single_file_change(loop, mocker):
    async def mock_awatch(path):
        yield {('x', '/path/to/file')}
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = mock_awatch

    app_task = AppTask(MagicMock(), loop)
    app_task._start_process = MagicMock()
    app_task.stop_process = MagicMock()
    app_task._app = MagicMock()
    await app_task._run()
    app_task._app.src_reload.assert_called_once_with('/path/to/file')
    assert app_task._start_process.call_count == 1
    assert app_task.stop_process.called is False
    app_task._session.close()


@pytest.mark.skipif(PY35, reason='no async generators in python 3.5')
async def test_multiple_file_change(loop, mocker):
    async def mock_awatch(path):
        yield {('x', '/path/to/file'), ('x', '/path/to/file2')}
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = mock_awatch
    app_task = AppTask(MagicMock(), loop)
    app_task._start_process = MagicMock()
    app_task.stop_process = MagicMock()

    app_task._app = MagicMock()
    await app_task._run()
    app_task._app.src_reload.assert_called_once_with()
    app_task._session.close()


@pytest.mark.skipif(PY35, reason='no async generators in python 3.5')
async def test_python_no_server(loop, mocker):
    async def mock_awatch(path):
        yield {('x', '/path/to/file.py')}
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = mock_awatch

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


@pytest.mark.skipif(PY35, reason='no async generators in python 3.5')
async def test_livereload_task_single(loop, mocker):
    async def mock_awatch(path):
        yield {('x', '/path/to/file')}
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = mock_awatch

    task = LiveReloadTask('x', loop)
    task._app = MagicMock()
    await task._run()
    task._app.src_reload.assert_called_once_with('/path/to/file')


@pytest.mark.skipif(PY35, reason='no async generators in python 3.5')
async def test_livereload_task_multiple(loop, mocker):
    async def mock_awatch(path):
        yield {('x', '/path/to/file'), ('x', '/path/to/file2')}
    mocked_awatch = mocker.patch('aiohttp_devtools.runserver.watch.awatch')
    mocked_awatch.side_effect = mock_awatch

    task = LiveReloadTask('x', loop)
    task._app = MagicMock()
    await task._run()
    task._app.src_reload.assert_called_once_with()
