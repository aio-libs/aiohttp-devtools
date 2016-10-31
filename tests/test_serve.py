import pytest

from aiohttp_devtools.runserver import serve_static

from .conftest import mktree


@pytest.yield_fixture
def cli(loop, tmpworkdir, test_client):
    app, observer, _ = serve_static(static_path=str(tmpworkdir), livereload=False, port=8000, loop=loop)
    yield loop.run_until_complete(test_client(app))

    # this doesn't seem necessary and slows down tests a lot
    # observer.stop()
    # observer.join()


async def test_simple_serve(cli, tmpworkdir):
    mktree(tmpworkdir, {
        'foo': 'hello world',
    })
    r = await cli.get('/foo')
    assert r.headers['content-type'] == 'application/octet-stream'
    assert r.status == 200
    text = await r.text()
    assert text == 'hello world'


async def test_file_missing(cli):
    r = await cli.get('/foo')
    assert r.status == 404
    text = await r.text()
    assert '404: Not Found\n\n' in text


async def test_html_file_livereload(loop, test_client, tmpworkdir):
    app, observer, _ = serve_static(static_path=str(tmpworkdir), livereload=True, port=8000, loop=loop)
    cli = await test_client(app)
    mktree(tmpworkdir, {
        'foo.html': '<h1>hi</h1>',
    })
    r = await cli.get('/foo')
    assert r.headers['content-type'] == 'text/html'
    assert r.status == 200
    text = await r.text()
    assert text == '<h1>hi</h1>\n<script src="http://localhost:8000/livereload.js"></script>\n'
    r = await cli.get('/livereload.js')
    assert r.headers['content-type'] == 'application/javascript'
    assert r.status == 200
    text = await r.text()
    assert text.startswith('(function e(t,n,r){')
