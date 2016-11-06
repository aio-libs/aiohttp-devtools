import sys
import traceback
from pathlib import Path

import click

from .exceptions import AiohttpDevException
from .logs import main_logger, setup_logging
from .runserver import runserver as _runserver
from .runserver import run_app, serve_static
from .start import Options, StartProject
from .version import VERSION

_dir_existing = click.Path(exists=True, dir_okay=True, file_okay=False)
_file_dir_existing = click.Path(exists=True, dir_okay=True, file_okay=True)
_dir_may_exist = click.Path(dir_okay=True, file_okay=False, writable=True, resolve_path=True)


@click.group()
@click.version_option(VERSION, '-V', '--version', prog_name='aiohttp-devtools')
def cli():
    pass


verbose_help = 'Enable verbose output.'
livereload_help = 'Whether to inject livereload.js into html page footers to autoreload on changes.'


@cli.command()
@click.argument('path', type=_dir_existing, required=True)
@click.option('--livereload/--no-livereload', default=True, help=livereload_help)
@click.option('-p', '--port', default=8000, type=int)
@click.option('-v', '--verbose', is_flag=True, help=verbose_help)
def serve(path, livereload, port, verbose):
    """
    Serve static files from a directory.
    """
    setup_logging(verbose)
    run_app(*serve_static(static_path=path, livereload=livereload, port=port))


static_help = "Path of static files to serve, if excluded static files aren't served."
static_url_help = 'URL path to serve static files from, default "/static/".'
debugtoolbar_help = 'Whether to enable debug toolbar.'
app_factory_help = ('name of the app factory to create an aiohttp.web.Application with, '
                    'if missing default app-factory names are tried.')
port_help = 'Port to serve app from, default 8000.'
aux_port_help = 'Port to serve auxiliary app (reload and static) on, default 8001.'


# defaults are all None here so default settings are defined in one place: DEV_DICT validation
@cli.command()
@click.argument('app-path', type=_file_dir_existing, required=True)
@click.option('-s', '--static', 'static_path', type=_dir_existing, help=static_help)
@click.option('--static-url', help=static_url_help)
@click.option('--livereload/--no-livereload', default=None, help=livereload_help)
@click.option('--debug-toolbar/--no-debug-toolbar', default=None, help=debugtoolbar_help)
@click.option('--app-factory', help=app_factory_help)
@click.option('-p', '--port', 'main_port', help=port_help)
@click.option('--aux-port', help=aux_port_help)
@click.option('-v', '--verbose', is_flag=True, help=verbose_help)
def runserver(**config):
    """
    Run a development server for aiohttp apps.

    Takes one argument "APP_PATH" which should be a path to either a directory containing a recognized default file
    ("settings.y(a)ml", "app.py" or "main.py") or to a specific file.

    If a yaml file is found the "dev" dictionary in that file is used to populate settings for runserver, if a python
    file is found it's run directly, see the "--app-factory" option for details on how an app is loaded from a python
    module.
    """
    setup_logging(config['verbose'])
    try:
        _runserver(**config)
        # run_app(*_runserver(**config))
    except AiohttpDevException as e:
        if config['verbose']:
            tb = click.style(traceback.format_exc().strip('\n'), fg='white', dim=True)
            main_logger.warning('AiohttpDevException traceback:\n%s', tb)
        main_logger.error('Error: %s', e)
        sys.exit(2)


class Choice2(click.Choice):
    def get_metavar(self, param):
        return '[{}*|{}]'.format(click.style(self.choices[0], bold=True), '|'.join(self.choices[1:]))


@cli.command()
@click.argument('path', type=_dir_may_exist, required=True)
@click.argument('name', required=False)
@click.option('--template-engine', type=Choice2(Options.TEMPLATE_ENG_CHOICES), default=Options.TEMPLATE_ENG_JINJA2)
@click.option('--session', type=Choice2(Options.SESSION_CHOICES), default=Options.SESSION_SECURE)
@click.option('--database', type=Choice2(Options.DB_CHOICES), default=Options.DB_PG_SA)
@click.option('--example', type=Choice2(Options.EXAMPLE_CHOICES), default=Options.EXAMPLE_MESSAGE_BOARD)
@click.option('-v', '--verbose', is_flag=True, help=verbose_help)
def start(*, path, name, template_engine, session, database, example, verbose):
    """
    Create a new aiohttp app.
    """
    setup_logging(verbose)
    if name is None:
        name = Path(path).name
    try:
        StartProject(path=path, name=name,
                     template_engine=template_engine, session=session, database=database, example=example)
    except AiohttpDevException as e:
        main_logger.error('Error: %s', e)
        sys.exit(2)
