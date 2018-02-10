import asyncio

from click.testing import CliRunner

from aiohttp_devtools.cli import cli
from aiohttp_devtools.exceptions import AiohttpDevException


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'Run a development server for an aiohttp apps.' in result.output
    assert 'Serve static files from a directory.' in result.output
    assert 'Create a new aiohttp app.' in result.output


def test_serve(mocker, loop):
    asyncio.set_event_loop(loop)
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
    assert 'Error: Missing argument "path"' in result.output


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


def test_runserver_no_args(loop):
    asyncio.set_event_loop(loop)
    runner = CliRunner()
    result = runner.invoke(cli, ['runserver'])
    assert result.exit_code == 2
    assert result.output.startswith('Error: unable to find a recognised default file')


def test_start(mocker):
    mock_start_project = mocker.patch('aiohttp_devtools.cli.StartProject')
    mocker.patch('aiohttp_devtools.cli.check_dir_clean')
    runner = CliRunner()
    result = runner.invoke(cli, ['start', 'foobar'])
    assert result.exit_code == 0
    assert mock_start_project.call_count == 1
    call_kwargs = mock_start_project.call_args[1]
    assert call_kwargs['path'].endswith('/foobar')
    assert call_kwargs['name'] == 'foobar'
    assert 'Please choose which database backend you wish to use.' in result.output
    assert 'using: pg-raw' not in result.output


def test_start_with_choice(mocker):
    mock_start_project = mocker.patch('aiohttp_devtools.cli.StartProject')
    mocker.patch('aiohttp_devtools.cli.check_dir_clean')
    runner = CliRunner()
    result = runner.invoke(cli, ['start', '--database', 'pg-sqlalchemy', 'foobar'])
    assert result.exit_code == 0
    assert mock_start_project.call_count == 1
    call_kwargs = mock_start_project.call_args[1]
    assert call_kwargs['path'].endswith('/foobar')
    assert call_kwargs['name'] == 'foobar'
    assert 'Please choose which database backend you wish to use.' not in result.output
    assert 'using: pg-sqlalchemy' in result.output


def test_start_different_name(mocker):
    mock_start_project = mocker.patch('aiohttp_devtools.cli.StartProject')
    mocker.patch('aiohttp_devtools.cli.check_dir_clean')
    runner = CliRunner()
    result = runner.invoke(cli, ['start', 'foobar', 'splosh'])
    assert result.exit_code == 0
    assert mock_start_project.call_count == 1
    call_kwargs = mock_start_project.call_args[1]
    assert call_kwargs['path'].endswith('/foobar')
    assert call_kwargs['name'] == 'splosh'


def test_start_error(mocker):
    mock_start_project = mocker.patch('aiohttp_devtools.cli.StartProject')
    mocker.patch('aiohttp_devtools.cli.check_dir_clean')
    mock_start_project.side_effect = AiohttpDevException('foobar')
    runner = CliRunner()
    result = runner.invoke(cli, ['start', 'foobar'])
    assert result.exit_code == 2
    assert mock_start_project.call_count == 1


def test_start_no_args():
    runner = CliRunner()
    result = runner.invoke(cli, ['start'])
    assert result.exit_code == 2
    assert 'Error: Missing argument "path"' in result.output


def test_start_help():
    runner = CliRunner()
    result = runner.invoke(cli, ['start', '--help'])
    assert result.exit_code == 0
    assert 'Create a new aiohttp app.' in result.output
    assert '--template-engine [jinja*|none]' in result.output
