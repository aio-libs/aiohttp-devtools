from pathlib import Path

import click

from .exceptions import AiohttpDevException
from .runserver.logs import setup_logging
from .runserver import runserver as _runserver
from .start import StartProject, Options
from .version import VERSION


@click.group()
@click.version_option(VERSION, '-V', '--version', prog_name='aiohttp-devtools')
def cli():
    pass


static_help = "Path of static files to serve, if excluded static files aren't served."
static_url_help = 'URL path to serve static files from, default "/static/".'
livereload_help = 'Whether to inject livereload.js into html page footers to autoreload on changes.'
debugtoolbar_help = 'Whether to enable debug toolbar.'
port_help = 'Port to serve app from, default 8000.'
aux_port_help = 'Port to serve auxiliary app (reload and static) on, default 8001.'
verbose_help = 'Enable verbose output.'

_static_path_type = click.Path(exists=True, dir_okay=True, file_okay=False)
_app_path_type = click.Path(exists=True, dir_okay=False, file_okay=True)


@cli.command()
@click.argument('app-path', type=_app_path_type, required=True)
@click.argument('app-factory', required=False)
@click.option('-s', '--static', 'static_path', type=_static_path_type, help=static_help)
@click.option('--static-url', default='/static/', help=static_url_help)
@click.option('--livereload/--no-livereload', default=True, help=livereload_help)
@click.option('--debug-toolbar/--debug-toolbar', default=True, help=debugtoolbar_help)
@click.option('-p', '--port', 'main_port', default=8000, help=port_help)
@click.option('--aux-port', default=8001, help=aux_port_help)
@click.option('-v', '--verbose', is_flag=True, help=verbose_help)
def runserver(**config):
    """
    Run a development server for a aiohttp app.
    """
    setup_logging(config['verbose'])
    _runserver(**config)

_path_type = click.Path(dir_okay=True, file_okay=False, writable=True, resolve_path=True)


@cli.command()
@click.argument('path', type=_path_type, required=True)
@click.argument('name', required=False)
@click.option('--template-engine', type=click.Choice(Options.TEMPLATE_ENG_CHOICES), default=Options.TEMPLATE_ENG_JINJA2)
@click.option('--session', type=click.Choice(Options.SESSION_CHOICES), default=Options.SESSION_SECURE)
@click.option('--database', type=click.Choice(Options.DB_CHOICES), default=Options.NONE)
@click.option('--example', type=click.Choice(Options.EXAMPLE_CHOICES), default=Options.EXAMPLE_MESSAGE_BOARD)
def start(*, path, name, template_engine, session, database, example):
    """
    Create a new aiohttp app.
    """
    if name is None:
        name = Path(path).name
    try:
        StartProject(path=path, name=name,
                     template_engine=template_engine, session=session, database=database, example=example)
    except AiohttpDevException as e:
        raise click.BadParameter(e)
