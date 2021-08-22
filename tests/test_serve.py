import asyncio

import pytest
from pytest_toolbox import mktree

from aiohttp_devtools.runserver import serve_static


@pytest.fixture
def cli(loop, tmpworkdir, aiohttp_client):
    asyncio.set_event_loop(loop)
    app, _, _ = serve_static(static_path=str(tmpworkdir), livereload=False)
    yield loop.run_until_complete(aiohttp_client(app))


async def test_simple_serve(cli, tmpworkdir):
    mktree(tmpworkdir, {
        'foo': 'hello world',
    })
    r = await cli.get('/foo')
    assert r.status == 200
    assert r.headers['content-type'] == 'application/octet-stream'
    assert 'Access-Control-Allow-Origin' in r.headers and r.headers['Access-Control-Allow-Origin'] == '*'
    text = await r.text()
    assert text == 'hello world'


async def test_file_missing(cli):
    r = await cli.get('/foo')
    assert r.status == 404
    text = await r.text()
    assert '404: Not Found\n' in text


async def test_html_file_livereload(loop, aiohttp_client, tmpworkdir):
    app, port, _ = serve_static(static_path=str(tmpworkdir), livereload=True)
    assert port == 8000
    cli = await aiohttp_client(app)
    mktree(tmpworkdir, {
        'foo.html': '<h1>hi</h1>',
    })
    r = await cli.get('/foo')
    assert r.status == 200
    assert r.headers['content-type'] == 'text/html'
    text = await r.text()
    assert text == '<h1>hi</h1>\n<script src="/livereload.js"></script>\n'
    r = await cli.get('/livereload.js')
    assert r.status == 200
    assert r.headers['content-type'] == 'application/javascript'
    text = await r.text()
    assert text.startswith('(function e(t,n,r){')


async def test_serve_index(loop, aiohttp_client, tmpworkdir):
    app, port, _ = serve_static(static_path=str(tmpworkdir), livereload=False)
    assert port == 8000
    cli = await aiohttp_client(app)
    mktree(tmpworkdir, {
        'index.html': '<h1>hello index</h1>',
    })
    r = await cli.get('/')
    assert r.status == 200
    assert r.headers['content-type'] == 'text/html'
    text = await r.text()
    assert text == '<h1>hello index</h1>'
