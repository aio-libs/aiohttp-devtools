from click.testing import CliRunner

from aiohttp_devtools.cli import cli


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'Run a development server for aiohttp apps.' in result.output
    assert 'Serve static files from a directory.' in result.output
    assert 'Create a new aiohttp app.' in result.output


def test_serve_no_args():
    runner = CliRunner()
    result = runner.invoke(cli, ['serve'])
    assert result.exit_code == 2
    assert 'Error: Missing argument "path"' in result.output


def test_runserver_no_args():
    runner = CliRunner()
    result = runner.invoke(cli, ['runserver'])
    assert result.exit_code == 2
    assert 'Missing argument "app-path"' in result.output


def test_start_no_args():
    runner = CliRunner()
    result = runner.invoke(cli, ['start'])
    assert result.exit_code == 2
    assert 'Error: Missing argument "path"' in result.output

