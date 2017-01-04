def pytest_addoption(parser):
    parser.addoption('--fast', action='store_true', help="don't run slow tests")


SIMPLE_APP = {
    'app.py': """\
from aiohttp import web

async def hello(request):
    return web.Response(text='hello world')

def create_app(loop):
    app = web.Application(loop=loop)
    app.router.add_get('/', hello)
    return app"""
}


def get_slow(_pytest):
    return _pytest.mark.skipif(_pytest.config.getoption('--fast'), reason='not run with --fast flag')
