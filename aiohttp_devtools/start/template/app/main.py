from aiohttp import web
from .routes import routes


def create_app(loop):
    app = web.Application(loop=loop)
    [app.router.add_route(*args) for args in routes]
    return app
