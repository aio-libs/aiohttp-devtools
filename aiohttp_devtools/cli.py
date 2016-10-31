from pathlib import Path

import click

from .exceptions import AiohttpDevException
from .logs import setup_logging
from .runserver import runserver as _runserver
from .runserver import BadSetup, run_app, serve_static
from .start import Options, StartProject
from .version import VERSION

_dir_existing = click.Path(exists=True, dir_okay=True, file_okay=False)
_file_existing = click.Path(exists=True, dir_okay=False, file_okay=True)
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
port_help = 'Port to serve app from, default 8000.'
aux_port_help = 'Port to serve auxiliary app (reload and static) on, default 8001.'


@cli.command()
@click.argument('app-path', type=_file_existing, required=True)
@click.argument('app-factory', required=False)
@click.option('-s', '--static', 'static_path', type=_dir_existing, help=static_help)
@click.option('--static-url', default='/static/', help=static_url_help)
@click.option('--livereload/--no-livereload', default=True, help=livereload_help)
@click.option('--debug-toolbar/--debug-toolbar', default=True, help=debugtoolbar_help)
@click.option('-p', '--port', 'main_port', default=8000, help=port_help)
@click.option('--aux-port', default=8001, help=aux_port_help)
@click.option('-v', '--verbose', is_flag=True, help=verbose_help)
def runserver(**config):
    """
    Run a development server for aiohttp apps.
    """
    setup_logging(config['verbose'])
    try:
        run_app(*_runserver(**config))
    except BadSetup as e:
        raise click.BadParameter(e) from e


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
        raise click.BadParameter(e) from e
