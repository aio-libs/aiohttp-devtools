import json
import logging
import logging.config
import platform
import re
import traceback
from io import StringIO
from types import TracebackType
from typing import Dict, Literal, Optional, Tuple, Type, Union

import pygments
from devtools import pformat
from devtools.ansi import sformat
from devtools.utils import isatty
from pygments.formatters import Terminal256Formatter
from pygments.lexers import Python3TracebackLexer

_Ei = Union[Tuple[Type[BaseException], BaseException, Optional[TracebackType]], Tuple[None, None, None]]

rs_dft_logger = logging.getLogger('adev.server.dft')
rs_aux_logger = logging.getLogger('adev.server.aux')

tools_logger = logging.getLogger('adev.tools')
main_logger = logging.getLogger('adev.main')

LOG_FORMATS = {
    logging.DEBUG: sformat.dim,
    logging.INFO: sformat.green,
    logging.WARN: sformat.yellow,
}
pyg_lexer = Python3TracebackLexer()
pyg_formatter = Terminal256Formatter(style='vim')
split_log = re.compile(r'^(\[.*?\])')


class DefaultFormatter(logging.Formatter):
    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None, style: Literal["%", "{", "$"] = "%"):
        super().__init__(fmt, datefmt, style)
        self.stream_is_tty = False

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        if not self.stream_is_tty:
            return msg
        m = split_log.match(msg)
        log_color = LOG_FORMATS.get(record.levelno, sformat.red)
        if m:
            time = sformat(m.groups()[0], sformat.magenta)
            return time + sformat(msg[m.end():], log_color)

        return sformat(msg, log_color)


class AccessFormatter(logging.Formatter):
    """Used to log aiohttp_access and aiohttp_server."""

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None, style: Literal["%", "{", "$"] = "%"):
        super().__init__(fmt, datefmt, style)
        self.stream_is_tty = False

    def formatMessage(self, record: logging.LogRecord) -> str:
        msg = super().formatMessage(record)
        if msg[0] != '{':
            return msg
        # json from AccessLogger
        obj = json.loads(msg)
        if self.stream_is_tty:
            # in future we can do clever things about colouring the message based on status code
            msg = '{} {} {}'.format(
                sformat(obj['time'], sformat.magenta),
                sformat(obj['prefix'], sformat.blue),
                sformat(obj['msg'], sformat.dim if obj['dim'] else sformat.reset),
            )
        else:
            msg = '{time} {prefix} {msg}'.format(**obj)
        details = getattr(record, 'details', None)
        if details:
            msg = 'details: {}\n{}'.format(pformat(details, highlight=self.stream_is_tty), msg)
        return msg

    def formatException(self, ei: _Ei) -> str:
        sio = StringIO()
        traceback.print_exception(*ei, file=sio)  # type: ignore[misc]
        stack = sio.getvalue()
        sio.close()
        if self.stream_is_tty and pyg_lexer:
            return pygments.highlight(stack, lexer=pyg_lexer, formatter=pyg_formatter).rstrip("\n")

        return stack


class HighlightStreamHandler(logging.StreamHandler):  # type: ignore[type-arg]
    def setFormatter(self, fmt: Optional[logging.Formatter]) -> None:
        stream_is_tty = isatty(self.stream) and platform.system().lower() != "windows"
        if isinstance(fmt, (DefaultFormatter, AccessFormatter)):
            fmt.stream_is_tty = stream_is_tty

        self.formatter = fmt


def log_config(verbose: bool) -> Dict[str, object]:
    """
    Setup default config. for dictConfig.
    :param verbose: level: DEBUG if True, INFO if False
    :return: dict suitable for ``logging.config.dictConfig``
    """
    log_level = 'DEBUG' if verbose else 'INFO'
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                'format': '[%(asctime)s] %(message)s',
                'datefmt': '%H:%M:%S',
                'class': 'aiohttp_devtools.logs.DefaultFormatter',
            },
            'no_ts': {
                'format': '%(message)s',
                'class': 'aiohttp_devtools.logs.DefaultFormatter',
            },
            'aiohttp': {
                'format': '%(message)s',
                'class': 'aiohttp_devtools.logs.AccessFormatter',
            },
        },
        'handlers': {
            'default': {
                'level': log_level,
                'class': 'aiohttp_devtools.logs.HighlightStreamHandler',
                'formatter': 'default'
            },
            'no_ts': {
                'level': log_level,
                'class': 'aiohttp_devtools.logs.HighlightStreamHandler',
                'formatter': 'no_ts'
            },
            'aiohttp_access': {
                'level': log_level,
                'class': 'aiohttp_devtools.logs.HighlightStreamHandler',
                'formatter': 'aiohttp'
            },
            'aiohttp_server': {
                'class': 'aiohttp_devtools.logs.HighlightStreamHandler',
                'formatter': 'aiohttp'
            },
        },
        'loggers': {
            rs_dft_logger.name: {
                'handlers': ['default'],
                'level': log_level,
            },
            rs_aux_logger.name: {
                'handlers': ['default'],
                'level': log_level,
            },
            tools_logger.name: {
                'handlers': ['default'],
                'level': log_level,
            },
            main_logger.name: {
                'handlers': ['no_ts'],
                'level': log_level,
            },
            'aiohttp.access': {
                'handlers': ['aiohttp_access'],
                'level': log_level,
                'propagate': False,
            },
            'aiohttp.server': {
                'handlers': ['aiohttp_server'],
                'level': log_level,
            },
        },
    }


def setup_logging(verbose: bool) -> None:
    config = log_config(verbose)
    logging.config.dictConfig(config)
