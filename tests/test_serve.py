import json
from pathlib import Path
from unittest import mock

import pytest
from aiohttp.web import WebSocketResponse

from aiohttp_devtools.runserver import serve_static
from aiohttp_devtools.runserver.serve import WS, src_reload


@pytest.fixture
async def cli(tmpworkdir, aiohttp_client):
    args = serve_static(static_path=str(tmpworkdir), livereload=False)
    yield await aiohttp_client(args["app"])


async def test_simple_serve(cli, mktree):
    mktree({
        'foo': 'hello world',
    })
    r = await cli.get('/foo')
    assert r.status == 200
    assert r.headers['content-type'] == 'application/octet-stream'
    assert 'Access-Control-Allow-Origin' in r.headers and r.headers['Access-Control-Allow-Origin'] == '*'
    assert r.headers["Cache-Control"] == "no-cache"
    text = await r.text()
    assert text == 'hello world'


async def test_file_missing(cli, mktree):
    mktree({
        "bar": "hello world",
        "baz/foo": "hello world",
    })
    r = await cli.get('/foo')
    assert r.status == 404
    text = await r.text()
    assert '404: Not Found\n' in text
    assert "bar\n" in text
    assert "baz/\n" in text


async def test_browser_cache(aiohttp_client, tmpworkdir, mktree):
    args = serve_static(static_path=str(tmpworkdir), browser_cache=True)
    assert args["port"] == 8000
    cli = await aiohttp_client(args["app"])
    mktree({"foo": "hello world"})
    r = await cli.get("/foo")
    assert r.status == 200
    assert "Cache-Control" not in r.headers


async def test_html_file_livereload(aiohttp_client, tmpworkdir, mktree):
    args = serve_static(static_path=str(tmpworkdir), livereload=True)
    assert args["port"] == 8000
    cli = await aiohttp_client(args["app"])
    mktree({
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
    assert text.startswith('(function(){function r(e,n,t)')


async def test_serve_index(aiohttp_client, tmpworkdir, mktree):
    args = serve_static(static_path=str(tmpworkdir), livereload=False)
    assert args["port"] == 8000
    cli = await aiohttp_client(args["app"])
    mktree({
        'index.html': '<h1>hello index</h1>',
    })
    r = await cli.get('/')
    assert r.status == 200
    assert r.headers['content-type'] == 'text/html'
    text = await r.text()
    assert text == '<h1>hello index</h1>'


async def test_serve_relative_path(tmpworkdir: Path) -> None:
    with mock.patch("aiohttp_devtools.runserver.main.LiveReloadTask", autospec=True, spec_set=True) as watcher:
        app = serve_static(static_path=".")["app"]
    # Changes are reported with absolute paths, so that is what must be watched and compared against.
    watcher.assert_called_once_with(str(tmpworkdir))
    ws = mock.create_autospec(WebSocketResponse, spec_set=True, instance=True)
    app[WS].add((ws, "/"))
    assert await src_reload(app, str(tmpworkdir / "foo.js")) == 1
    assert json.loads(ws.send_str.call_args[0][0])["path"] == str(Path("/foo.js"))
