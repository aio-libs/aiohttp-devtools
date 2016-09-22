import click

from .runserver.logs import setup_logging
from .runserver.main import run_apps
from .version import VERSION


@click.group()
def cli(**config):
    pass


static_help = "Path of static files to serve, if excluded static files aren't served."
static_url_help = 'URL path to serve static files from, default "/static/".'
livereload_help = 'Whether to inject livereload.js into html page footers to autoreload on changes.'
port_help = 'Port to serve app from, default 8000.'
aux_port_help = 'Port to serve auxiliary app (reload and static) on, default 8001.'
verbose_help = 'Enable verbose output.'

static_path_type = click.Path(exists=True, dir_okay=True, file_okay=False)


@cli.command()
@click.version_option(VERSION, '-V', '--version', prog_name='aiohttp-runserver')
@click.argument('app-path', type=click.Path(exists=True, dir_okay=False, file_okay=True), required=True)
@click.argument('app-factory', required=False)
@click.option('-s', '--static', 'static_path', type=static_path_type, help=static_help)
@click.option('--static-url', default='/static/', help=static_url_help)
@click.option('--livereload/--no-livereload', default=True, help=livereload_help)
@click.option('-p', '--port', 'main_port', default=8000, help=port_help)
@click.option('--aux-port', default=8001, help=aux_port_help)
@click.option('-v', '--verbose', is_flag=True, help=verbose_help)
def runserver(**config):
    """
    Development server for aiohttp apps.
    """
    setup_logging(config['verbose'])
    run_apps(**config)
