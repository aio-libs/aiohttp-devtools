import logging
from typing import Iterator

import pytest
from click.testing import CliRunner

from aiohttp_devtools.cli import cli
from aiohttp_devtools.exceptions import AiohttpDevException


@pytest.fixture(autouse=True)
def restore_logging() -> Iterator[None]:
    """Undo the logging configuration applied by the commands, so it doesn't leak into other tests."""
    state = [(logger, logger.level, logger.propagate, logger.handlers.copy())
             for logger in logging.Logger.manager.loggerDict.values() if isinstance(logger, logging.Logger)]
    yield
    for logger, level, propagate, handlers in state:
        logger.setLevel(level)
        logger.propagate = propagate
        logger.handlers[:] = handlers


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'Run a development server for an aiohttp apps.' in result.output
    assert 'Serve static files from a directory.' in result.output


def test_serve(mocker):
    mock_run_app = mocker.patch('aiohttp_devtools.cli.run_app')
    runner = CliRunner()
    result = runner.invoke(cli, ['serve', '.'])
    assert result.exit_code == 0
    assert 'Serving "." at http://localhost:8000, livereload ON' in result.output
    assert mock_run_app.call_count == 1


def test_serve_no_args():
    runner = CliRunner()
    result = runner.invoke(cli, ['serve'])
    assert result.exit_code == 2
    assert "Error: Missing argument 'PATH'" in result.output


def test_runserver(mocker):
    mock_run_app = mocker.patch('aiohttp_devtools.cli.run_app')
    mock_runserver = mocker.patch('aiohttp_devtools.cli._runserver')
    runner = CliRunner()
    result = runner.invoke(cli, ['runserver', '.'])
    assert result.exit_code == 0, result.output
    assert '' == result.output
    assert mock_run_app.call_count == 1
    assert mock_runserver.call_count == 1


def test_runserver_error(mocker):
    mock_run_app = mocker.patch('aiohttp_devtools.cli.run_app')
    mock_run_app.side_effect = AiohttpDevException('foobar')
    mock_runserver = mocker.patch('aiohttp_devtools.cli._runserver')
    runner = CliRunner()
    result = runner.invoke(cli, ['runserver', '.'])
    assert result.exit_code == 2
    assert 'Error: foobar\n' == result.output
    assert mock_run_app.call_count == 1
    assert mock_runserver.call_count == 1


def test_runserver_error_verbose(mocker):
    mock_run_app = mocker.patch('aiohttp_devtools.cli.run_app')
    mock_run_app.side_effect = AiohttpDevException('foobar')
    mock_runserver = mocker.patch('aiohttp_devtools.cli._runserver')
    runner = CliRunner()
    result = runner.invoke(cli, ['runserver', '.', '--verbose'])
    assert result.exit_code == 2
    assert 'Error: foobar\n' in result.output
    assert 'aiohttp_devtools.exceptions.AiohttpDevException: foobar' in result.output
    assert mock_run_app.call_count == 1
    assert mock_runserver.call_count == 1


def test_runserver_no_args():
    runner = CliRunner()
    result = runner.invoke(cli, ['runserver'])
    assert result.exit_code == 2
    assert result.output.startswith('Error: unable to find a recognised default file')
