import logging
from unittest.mock import MagicMock

from aiohttp_devtools.runserver.log_handlers import AiohttpAccessHandler, AuxiliaryHandler


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


def test_aiohttp_std(capsys):
    handler = AiohttpAccessHandler()
    record = _get_record('[foo] POST /foo X 200 123')
    handler.emit(record)
    out, err = capsys.readouterr()
    # no difference, could do better
    assert '[foo] ● POST /foo 200 123B\n' == out


def test_aiohttp_debugtoolbar(capsys):
    handler = AiohttpAccessHandler()
    record = _get_record('[foo] POST /_debugtoolbar/whatever X 200 123')
    handler.emit(record)
    out, err = capsys.readouterr()
    # no difference, could do better
    assert '[foo] ● POST /_debugtoolbar/whatever 200 123B\n' == out
