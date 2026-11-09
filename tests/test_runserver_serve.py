import json
import logging
import pathlib
import socket
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest
from aiohttp.web import Application, AppKey, Request, Response
from aiohttp_jinja2 import static_root_key

from aiohttp_devtools.exceptions import AiohttpDevException
from aiohttp_devtools.runserver.config import Config
from aiohttp_devtools.runserver.log_handlers import fmt_size
from aiohttp_devtools.runserver.serve import (
    LAST_RELOAD, STATIC_PATH, STATIC_URL, WS, check_port_open, cleanup_aux_app,
    modify_main_app, src_reload)

from .conftest import SIMPLE_APP, create_future


async def test_check_port_open(unused_tcp_port_factory):
    port = unused_tcp_port_factory()
    await check_port_open(port, host="127.0.0.1", delay=0.001)


async def test_check_port_not_open(unused_tcp_port_factory):
    port = unused_tcp_port_factory()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))
        with pytest.raises(AiohttpDevException):
            await check_port_open(port, host="127.0.0.1", delay=0.001)


async def test_aux_reload(caplog):
    aux_app = Application()
    ws = MagicMock()
    ws.send_str = MagicMock(return_value=create_future())
    aux_app[LAST_RELOAD] = [0, 0.]
    aux_app[STATIC_PATH] = "/path/to/static_files/"
    aux_app[STATIC_URL] = "/static/"
    aux_app[WS] = set(((ws, "/foo/bar"),))  # type: ignore[misc]
    assert 1 == await src_reload(aux_app, '/path/to/static_files/the_file.js')
    assert ws.send_str.call_count == 1
    send_obj = json.loads(ws.send_str.call_args[0][0])
    expected_path = str(pathlib.Path('/static/the_file.js'))
    assert send_obj == {
        'command': 'reload',
        'path': expected_path,
        'liveCSS': True,
        'liveImg': True,
    }
    assert caplog.record_tuples == [
        ("adev.server.aux", logging.INFO, "prompted reload of {} on 1 client".format(expected_path))
    ]


async def test_aux_reload_no_path():
    aux_app = Application()
    ws = MagicMock()
    ws.send_str = MagicMock(return_value=create_future())
    aux_app[LAST_RELOAD] = [0, 0.]
    aux_app[STATIC_PATH] = "/path/to/static_files/"
    aux_app[STATIC_URL] = "/static/"
    aux_app[WS] = set(((ws, "/foo/bar"),))  # type: ignore[misc]
    assert 1 == await src_reload(aux_app)
    assert ws.send_str.call_count == 1
    send_obj = json.loads(ws.send_str.call_args[0][0])
    assert send_obj == {
        'command': 'reload',
        'path': '/foo/bar',
        'liveCSS': True,
        'liveImg': True,
    }


async def test_aux_reload_html_different():
    aux_app = Application()
    ws = MagicMock()
    ws.send_str = MagicMock(return_value=create_future())
    aux_app[LAST_RELOAD] = [0, 0.]
    aux_app[STATIC_PATH] = "/path/to/static_files/"
    aux_app[STATIC_URL] = "/static/"
    aux_app[WS] = set(((ws, "/foo/bar"),))  # type: ignore[misc]
    assert 0 == await src_reload(aux_app, '/path/to/static_files/foo/bar.html')
    assert ws.send_str.call_count == 0


async def test_aux_reload_runtime_error(caplog):
    aux_app = Application()
    ws = MagicMock()
    ws.send_str = MagicMock(return_value=create_future())
    ws.send_str = MagicMock(side_effect=RuntimeError('foobar'))
    aux_app[LAST_RELOAD] = [0, 0.]
    aux_app[STATIC_PATH] = "/path/to/static_files/"
    aux_app[STATIC_URL] = "/static/"
    aux_app[WS] = set(((ws, "/foo/bar"),))  # type: ignore[misc]
    assert 0 == await src_reload(aux_app)
    assert ws.send_str.call_count == 1
    assert caplog.record_tuples == [
        ("adev.server.aux", logging.ERROR, "Error broadcasting change to /foo/bar, RuntimeError: foobar")
    ]


async def test_aux_cleanup():
    aux_app = Application()
    aux_app.on_cleanup.append(cleanup_aux_app)
    ws = MagicMock()
    ws.close = MagicMock(return_value=create_future())
    aux_app[WS] = set(((ws, "/foo/bar"),))  # type: ignore[misc]
    aux_app.freeze()
    await aux_app.cleanup()
    assert ws.close.call_count == 1


@pytest.mark.parametrize('value,result', [
    (None, ''),
    ('', ''),
    (1000, '1000B'),
    (2000, '2.0KB'),
])
def test_fmt_size_large(value, result):
    assert fmt_size(value) == result


class DummyApplication(Dict[AppKey[Any], object]):
    def __init__(self):
        self.on_response_prepare = []
        self.middlewares = []
        self.router = MagicMock()
        self[static_root_key] = '/static/'
        self._subapps = []

    def add_subapp(self, path, app):
        self._subapps.append(app)


def test_modify_main_app_all_off(mktree):
    mktree(SIMPLE_APP)
    config = Config(app_path="app.py", livereload=False, host="foobar.com",
                    static_path=".", browser_cache=True)
    app = DummyApplication()
    subapp = DummyApplication()
    app.add_subapp("/sub/", subapp)
    modify_main_app(app, config)  # type: ignore[arg-type]
    assert len(app.on_response_prepare) == 0
    assert len(app.middlewares) == 0
    assert app[static_root_key] == "http://foobar.com:8001/static"
    assert subapp[static_root_key] == "http://foobar.com:8001/static"


def test_modify_main_app_all_on(mktree):
    mktree(SIMPLE_APP)
    config = Config(app_path='app.py', static_path='.')
    app = DummyApplication()
    subapp = DummyApplication()
    app.add_subapp("/sub/", subapp)
    modify_main_app(app, config)  # type: ignore[arg-type]
    assert len(app.on_response_prepare) == 1
    assert len(app.middlewares) == 2
    assert app[static_root_key] == "http://localhost:8001/static"
    assert subapp[static_root_key] == "http://localhost:8001/static"


async def test_modify_main_app_on_prepare(mktree):
    mktree(SIMPLE_APP)
    config = Config(app_path='app.py', host='foobar.com')
    app = DummyApplication()
    modify_main_app(app, config)  # type: ignore[arg-type]
    on_prepare = app.on_response_prepare[0]
    request = MagicMock(spec=Request)
    request.path = '/'
    response = MagicMock(spec=Response)
    response.body = b'<h1>body</h1>'
    response.content_type = 'text/html'
    await on_prepare(request, response)
    assert response.body == b'<h1>body</h1>\n<script src="http://foobar.com:8001/livereload.js"></script>\n'
