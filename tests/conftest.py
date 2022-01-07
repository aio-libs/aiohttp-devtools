from asyncio import Future

import pytest


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
