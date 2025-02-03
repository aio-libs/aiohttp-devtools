import sys
from asyncio import Future

import pytest

if sys.platform == "win32":
    forked = pytest.mark.skip(reason="Windows doesn't suport fork")
else:
    forked = pytest.mark.forked

if sys.platform == 'linux':
    linux_forked = pytest.mark.forked
else:
    def linux_forked(func):
        return func    

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
