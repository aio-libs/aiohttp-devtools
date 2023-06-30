import asyncio

import pytest
from pytest_toolbox import mktree

from aiohttp_devtools.runserver import serve_static


@pytest.fixture
def cli(event_loop, tmpworkdir, aiohttp_client):
    asyncio.set_event_loop(event_loop)
    args = serve_static(static_path=str(tmpworkdir), livereload=False)
    yield event_loop.run_until_complete(aiohttp_client(args["app"]))


async def test_simple_serve(cli, tmpworkdir):
    mktree(tmpworkdir, {
        'foo': 'hello world',
    })
    r = await cli.get('/foo')
    assert r.status == 200
    assert r.headers['content-type'] == 'application/octet-stream'
    assert 'Access-Control-Allow-Origin' in r.headers and r.headers['Access-Control-Allow-Origin'] == '*'
    assert r.headers["Cache-Control"] == "no-cache"
    text = await r.text()
    assert text == 'hello world'


async def test_file_missing(cli, tmpworkdir):
    mktree(tmpworkdir, {
        "bar": "hello world",
        "baz/foo": "hello world",
    })
    r = await cli.get('/foo')
    assert r.status == 404
    text = await r.text()
    assert '404: Not Found\n' in text
    assert "bar\n" in text
    assert "baz/\n" in text


async def test_browser_cache(event_loop, aiohttp_client, tmpworkdir):
    args = serve_static(static_path=str(tmpworkdir), browser_cache=True)
    assert args["port"] == 8000
    cli = await aiohttp_client(args["app"])
    mktree(tmpworkdir, {"foo": "hello world"})
    r = await cli.get("/foo")
    assert r.status == 200
    assert "Cache-Control" not in r.headers


async def test_html_file_livereload(event_loop, aiohttp_client, tmpworkdir):
    args = serve_static(static_path=str(tmpworkdir), livereload=True)
    assert args["port"] == 8000
    cli = await aiohttp_client(args["app"])
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


async def test_serve_index(event_loop, aiohttp_client, tmpworkdir):
    args = serve_static(static_path=str(tmpworkdir), livereload=False)
    assert args["port"] == 8000
    cli = await aiohttp_client(args["app"])
    mktree(tmpworkdir, {
        'index.html': '<h1>hello index</h1>',
    })
    r = await cli.get('/')
    assert r.status == 200
    assert r.headers['content-type'] == 'text/html'
    text = await r.text()
    assert text == '<h1>hello index</h1>'
