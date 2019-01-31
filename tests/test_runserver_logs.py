import logging
import re
from unittest.mock import MagicMock

from aiohttp_devtools.runserver.log_handlers import AccessLogger


def _get_record(msg, level=logging.INFO):
    record = MagicMock()
    record.levelno = level
    record.exc_info = None
    record.exc_text = None
    record.stack_info = None
    record.getMessage = MagicMock(return_value=msg)
    return record


def _strip_ansi(v):
    return re.sub(r'\033\[((?:\d|;)*)([a-zA-Z])', '', v)


def test_aiohttp_std():
    info = MagicMock()
    logger = type('Logger', (), {'info': info})
    logger = AccessLogger(logger, None)
    request = MagicMock()
    request.method = 'GET'
    request.path_qs = '/foobar?v=1'
    response = MagicMock()
    response.status = 200
    response.body_length = 100
    logger.log(request, response, 0.15)
    assert info.call_count == 1
    msg = info.call_args[0][0]
    msg_stripped = _strip_ansi(msg)
    assert msg_stripped[msg_stripped.find(']'):] == ']● GET /foobar?v=1 200 100B 150ms'
    assert re.match(r'^\[\d\d:\d\d:\d\d\]', msg_stripped), msg_stripped
    # not dim
    assert '\x1b[2m' not in msg


def test_aiohttp_debugtoolbar():
    info = MagicMock()
    logger = type('Logger', (), {'info': info})
    logger = AccessLogger(logger, None)
    request = MagicMock()
    request.method = 'GET'
    request.path_qs = '/_debugtoolbar/whatever'
    response = MagicMock()
    response.status = 200
    response.body_length = 100
    logger.log(request, response, 0.15)
    assert info.call_count == 1
    msg = info.call_args[0][0]
    msg_stripped = _strip_ansi(msg)
    assert msg_stripped[msg_stripped.find(']'):] == ']● GET /_debugtoolbar/whatever 200 100B 150ms'
    assert re.match(r'^\[\d\d:\d\d:\d\d\]', msg_stripped), msg_stripped
    # dim
    assert '\x1b[2m' in msg
