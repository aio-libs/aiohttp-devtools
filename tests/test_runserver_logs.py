import json
import logging
import re
import sys
from unittest.mock import MagicMock

from aiohttp import web
import pytest

from aiohttp_devtools.logs import AccessFormatter, DefaultFormatter
from aiohttp_devtools.runserver.log_handlers import AccessLogger, AuxAccessLogger, parse_body


def test_aiohttp_std():
    info = MagicMock()
    logger_type = type("Logger", (), {"info": info})
    logger = AccessLogger(logger_type(), "")
    request = MagicMock()
    request.method = 'GET'
    request.path_qs = '/foobar?v=1'
    response = MagicMock()
    response.status = 200
    response.body_length = 100
    logger.log(request, response, 0.15)
    assert info.call_count == 1
    log = json.loads(info.call_args[0][0])
    time = log.pop('time')
    assert re.fullmatch(r'\[\d\d:\d\d:\d\d\]', time)
    assert log == {
        'prefix': '●',
        'msg': 'GET /foobar?v=1 200 100B 150ms',
        'dim': False,
    }


def test_aiohttp_debugtoolbar():
    info = MagicMock()
    logger_type = type("Logger", (), {"info": info})
    logger = AccessLogger(logger_type(), "")
    request = MagicMock()
    request.method = 'GET'
    request.path_qs = '/_debugtoolbar/whatever'
    response = MagicMock()
    response.status = 200
    response.body_length = 100
    logger.log(request, response, 0.15)
    assert info.call_count == 1
    log = json.loads(info.call_args[0][0])
    time = log.pop('time')
    assert re.fullmatch(r'\[\d\d:\d\d:\d\d\]', time)
    assert log == {
        'prefix': '●',
        'msg': 'GET /_debugtoolbar/whatever 200 100B 150ms',
        'dim': True,
    }


def test_aux_logger():
    info = MagicMock()
    logger_type = type("Logger", (), {"info": info})
    logger = AuxAccessLogger(logger_type(), "")
    request = MagicMock()
    request.method = 'GET'
    request.path = '/'
    request.path_qs = '/'
    response = MagicMock()
    response.status = 200
    response.body_length = 100
    logger.log(request, response, 0.15)
    assert info.call_count == 1
    log = json.loads(info.call_args[0][0])
    time = log.pop('time')
    assert re.fullmatch(r'\[\d\d:\d\d:\d\d\]', time)
    assert log == {
        'prefix': '◆',
        'msg': 'GET / 200 100B',
        'dim': False,
    }


def test_aux_logger_livereload():
    info = MagicMock()
    logger_type = type("Logger", (), {"info": info})
    logger = AuxAccessLogger(logger_type(), "")
    request = MagicMock()
    request.method = 'GET'
    request.path = '/livereload.js'
    request.path_qs = '/livereload.js'
    response = MagicMock()
    response.status = 200
    response.body_length = 100
    logger.log(request, response, 0.15)
    assert info.call_count == 0


def test_extra():
    info = MagicMock()
    logger_type = type("Logger", (), {"info": info})
    logger = AccessLogger(logger_type(), "")
    request = MagicMock(spec=web.Request)
    request.method = 'GET'
    request.headers = {'Foo': 'Bar'}
    request.path_qs = '/foobar?v=1'
    request._read_bytes = b'testing'
    response = MagicMock(spec=web.Response)
    response.status = 500
    response.body_length = 100
    response.headers = {'Foo': 'Spam'}
    response.text = 'testing'
    logger.log(request, response, 0.15)
    assert info.call_count == 1
    assert info.call_args[1]['extra'] == {
        'details': {
            'request_duration_ms': 150.0,
            'request_headers': {
                'Foo': 'Bar',
            },
            'request_body': b'testing',
            'request_size': '7B',
            'response_headers': {
                'Foo': 'Spam',
            },
            'response_body': 'testing',
        }
    }


@pytest.mark.parametrize('value,result', [
    (None, None),
    ('foobar', 'foobar'),
    (b'foobar', b'foobar'),
    ('{"foo": "bar"}', {'foo': 'bar'}),
])
def test_parse_body(value, result):
    assert parse_body(value, 'testing') == result


def test_parse_body_unicode_decode():
    with pytest.warns(UserWarning):
        assert parse_body(b'will fail: \x80', 'testing') == 'will fail: '


def _mk_record(msg, level=logging.INFO, **extra):
    class Record:
        levelno = level
        exc_info = None
        exc_text = None
        stack_info = None

        def __init__(self):
            if extra:
                for k, v in extra.items():
                    setattr(self, k, v)

        def getMessage(self):
            return msg
    return Record()


def test_dft_formatter():
    f = DefaultFormatter()
    assert f.format(_mk_record('testing')) == 'testing'


def test_dft_formatter_colour():
    f = DefaultFormatter()
    f.stream_is_tty = True
    assert f.format(_mk_record('testing')) == '\x1b[32mtesting\x1b[0m'


def test_dft_formatter_colour_time():
    f = DefaultFormatter()
    f.stream_is_tty = True
    assert f.format(_mk_record('[time] testing')) == '\x1b[35m[time]\x1b[0m\x1b[32m testing\x1b[0m'


def test_access_formatter():
    f = AccessFormatter()
    msg = json.dumps({'time': '_time_', 'prefix': '_p_', 'msg': '_msg_', 'dim': False})
    assert f.format(_mk_record(msg)) == '_time_ _p_ _msg_'


def test_access_formatter_no_json():
    f = AccessFormatter()
    assert f.format(_mk_record('foobar')) == 'foobar'


def test_access_formatter_colour():
    f = AccessFormatter()
    f.stream_is_tty = True
    msg = json.dumps({'time': '_time_', 'prefix': '_p_', 'msg': '_msg_', 'dim': False})
    assert f.format(_mk_record(msg)) == '\x1b[35m_time_\x1b[0m \x1b[34m_p_\x1b[0m \x1b[0m_msg_\x1b[0m'


def test_access_formatter_extra():
    f = AccessFormatter()
    msg = json.dumps({'time': '_time_', 'prefix': '_p_', 'msg': '_msg_', 'dim': False})
    assert f.format(_mk_record(msg, details={'foo': 'bar'})) == (
        'details: {\n'
        "    'foo': 'bar',\n"
        '}\n'
        '_time_ _p_ _msg_'
    )


def test_access_formatter_exc():
    f = AccessFormatter()
    try:
        raise RuntimeError('testing')
    except RuntimeError:
        stack = f.formatException(sys.exc_info())
        assert stack.startswith('Traceback (most recent call last):\n')
        assert stack.endswith('RuntimeError: testing\n')


def test_access_formatter_exc_colour():
    f = AccessFormatter()
    f.stream_is_tty = True
    try:
        raise RuntimeError('testing')
    except RuntimeError:
        stack = f.formatException(sys.exc_info())
        assert stack.startswith('\x1b[38;5;26mTraceback')
