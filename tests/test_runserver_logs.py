import logging
import re
from unittest.mock import MagicMock

from aiohttp_devtools.runserver.log_handlers import AccessLogger, AuxiliaryHandler


def _get_record(msg, level=logging.INFO):
    record = MagicMock()
    record.levelno = level
    record.exc_info = None
    record.exc_text = None
    record.stack_info = None
    record.getMessage = MagicMock(return_value=msg)
    return record


def test_aux_std(capsys):
    handler = AuxiliaryHandler()
    record = _get_record('[foo] bar')
    handler.emit(record)
    out, err = capsys.readouterr()
    assert '[foo] bar\n' == out


def test_aux_request(capsys):
    handler = AuxiliaryHandler()
    record = _get_record('[foo] > bar')
    handler.emit(record)
    out, err = capsys.readouterr()
    assert '[foo] ◆ bar\n' == out


def test_aux_request_304(capsys):
    handler = AuxiliaryHandler()
    record = _get_record('[foo] > bar 304 0B')
    handler.emit(record)
    out, err = capsys.readouterr()
    # no difference, could do better
    assert '[foo] ◆ bar 304 0B\n' == out


def _strip_ansi(v):
    return re.sub(r'\033\[((?:\d|;)*)([a-zA-Z])', '', v)


def test_aiohttp_std():
    info = MagicMock()
    logger = type('Logger', (), {'info': info})
    handler = AccessLogger(logger, None)
    request = MagicMock()
    request.method = 'GET'
    request.path = '/foobar?v=1'
    response = MagicMock()
    response.status = 200
    response.body_length = 100
    handler.log(request, response, 0.15)
    assert info.call_count == 1
    msg = _strip_ansi(info.call_args[0][0])
    assert msg[msg.find(']'):] == ']● GET /foobar?v=1 200 100B 150ms'
    assert re.match(r'^\[\d\d:\d\d:\d\d\]', msg), msg
    # not dim
    assert '\x1b[2m' not in info.call_args[0][0]


def test_aiohttp_debugtoolbar():
    info = MagicMock()
    logger = type('Logger', (), {'info': info})
    handler = AccessLogger(logger, None)
    request = MagicMock()
    request.method = 'GET'
    request.path = '/_debugtoolbar/whatever'
    response = MagicMock()
    response.status = 200
    response.body_length = 100
    handler.log(request, response, 0.15)
    assert info.call_count == 1
    msg = _strip_ansi(info.call_args[0][0])
    assert msg[msg.find(']'):] == ']● GET /_debugtoolbar/whatever 200 100B 150ms'
    assert re.match(r'^\[\d\d:\d\d:\d\d\]', msg), msg
    # dim
    assert '\x1b[2m' in info.call_args[0][0]
