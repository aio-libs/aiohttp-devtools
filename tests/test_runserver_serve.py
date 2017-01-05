import asyncio
import json
import socket
from unittest.mock import MagicMock

import pytest

from aiohttp_devtools.exceptions import AiohttpDevException
from aiohttp_devtools.runserver.serve import AuxiliaryApplication, check_port_open


async def test_check_port_open(unused_port, loop):
    port = unused_port()
    await check_port_open(port, loop, 0.001)


async def test_check_port_not_open(unused_port, loop):
    port = unused_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('0.0.0.0', port))
        with pytest.raises(AiohttpDevException):
            await check_port_open(port, loop, 0.001)


def test_aux_reload(loop, caplog):
    aux_app = AuxiliaryApplication(loop=loop)
    ws = MagicMock()
    aux_app.update(
        websockets=[(ws, '/foo/bar')],
        static_url='/static/',
        static_path='/path/to/static_files/'
    )
    assert aux_app.src_reload('/path/to/static_files/the_file.js') == 1
    assert ws.send_str.call_count == 1
    send_obj = json.loads(ws.send_str.call_args[0][0])
    assert send_obj == {
        'command': 'reload',
        'path': '/static/the_file.js',
        'liveCSS': True,
        'liveImg': True,
    }
    assert 'adev.server.aux INFO: prompted reload of /static/the_file.js on 1 client\n' == caplog


def test_aux_reload_no_path(loop):
    aux_app = AuxiliaryApplication(loop=loop)
    ws = MagicMock()
    aux_app.update(
        websockets=[(ws, '/foo/bar')],
        static_url='/static/',
        static_path='/path/to/static_files/'
    )
    assert aux_app.src_reload() == 1
    assert ws.send_str.call_count == 1
    send_obj = json.loads(ws.send_str.call_args[0][0])
    assert send_obj == {
        'command': 'reload',
        'path': '/foo/bar',
        'liveCSS': True,
        'liveImg': True,
    }


def test_aux_reload_html_different(loop):
    aux_app = AuxiliaryApplication(loop=loop)
    ws = MagicMock()
    aux_app.update(
        websockets=[(ws, '/foo/bar')],
        static_url='/static/',
        static_path='/path/to/static_files/'
    )
    assert aux_app.src_reload('/path/to/static_files/foo/bar.html') == 0
    assert ws.send_str.call_count == 0


def test_aux_reload_runtime_error(loop, caplog):
    aux_app = AuxiliaryApplication(loop=loop)
    ws = MagicMock()
    ws.send_str = MagicMock(side_effect=RuntimeError('foobar'))
    aux_app.update(
        websockets=[(ws, '/foo/bar')],
        static_url='/static/',
        static_path='/path/to/static_files/'
    )
    assert aux_app.src_reload() == 0
    assert ws.send_str.call_count == 1
    assert 'adev.server.aux ERROR: Error broadcasting change to /foo/bar, RuntimeError: foobar\n' == caplog


async def test_aux_cleanup(loop):
    aux_app = AuxiliaryApplication(loop=loop)
    ws = MagicMock()
    f = asyncio.Future(loop=loop)
    f.set_result(1)
    ws.close = MagicMock(return_value=f)
    aux_app['websockets'] = [(ws, '/foo/bar')]
    await aux_app.cleanup()
    assert ws.close.call_count == 1
