from asyncio import Future


def pytest_addoption(parser):
    try:
        parser.addoption('--fast', action='store_true', help="don't run slow tests")
    except ValueError:
        # --fast is already defined by aiohttp
        pass


SIMPLE_APP = {
    'app.py': """\
from aiohttp import web


async def hello(request):
    return web.Response(text='hello world')

def create_app():
    app = web.Application()
    app.router.add_get('/', hello)
    return app"""
}


def get_slow(_pytest):
    return _pytest.mark.skipif(_pytest.config.getoption('--fast'), reason='not run with --fast flag')


def get_if_boxed(_pytest):
    return _pytest.mark.skipif(not _pytest.config.getoption('--boxed'), reason='only run with --boxed flag')


def create_future(result=None):
    f = Future()
    f.set_result(result)
    return f
