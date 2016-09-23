from pathlib import Path
# {% if template_engine.is_jinja2 %}
import aiohttp_jinja2
from aiohttp_jinja2 import APP_KEY as JINJA2_APP_KEY
import jinja2
# {% endif %}
from aiohttp import web

from .routes import setup_routes

THIS_DIR = Path(__file__).parent
# {% if template_engine.is_jinja2 %}

@jinja2.contextfilter
def reverse_url(context, name, **parts):
    app = context['app']

    kwargs = {}
    if 'query' in parts:
        kwargs['query'] = parts.pop('query')
    if parts:
        kwargs['parts'] = parts
    return app.router[name].url(**kwargs)


@jinja2.contextfilter
def static_url(context, static_file):
    app = context['app']
    try:
        static_url = app['static_url']
    except KeyError:
        raise RuntimeError('app does not define a static root url "static_url"')
    return '{}/{}'.format(static_url.rstrip('/'), static_file.lstrip('/'))
# {% endif %}


def create_app(loop):
    app = web.Application(loop=loop)
    app['name'] = '{{ name }}'
    # {% if template_engine.is_jinja2 %}

    jinja2_loader = jinja2.FileSystemLoader(str(THIS_DIR / 'templates'))
    aiohttp_jinja2.setup(app, loader=jinja2_loader, app_key=JINJA2_APP_KEY)
    app[JINJA2_APP_KEY].filters.update(
        url=reverse_url,
        static=static_url,
    )
    # {% endif %}

    setup_routes(app)
    return app
