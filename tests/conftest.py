from asyncio import Future

import pytest


def pytest_collection_modifyitems(config, items):
    if not config.getoption('--boxed'):
        skip_boxed = pytest.mark.skip(reason='only run with --boxed flag')
        for item in items:
            if 'boxed' in item.keywords:
                item.add_marker(skip_boxed)


def pytest_addoption(parser):
    parser.addoption("--boxed", action="store_true", help="Run boxed tests")
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


def create_future(result=None):
    f: Future[None] = Future()
    f.set_result(result)
    return f
