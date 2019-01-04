import logging
import logging.config
import re
import traceback
from io import StringIO

import click
import pygments
from pygments.lexers import Python3TracebackLexer
from pygments.formatters import Terminal256Formatter
from devtools import pformat as format_extra
from devtools.ansi import isatty

rs_dft_logger = logging.getLogger('adev.server.dft')
rs_aux_logger = logging.getLogger('adev.server.aux')

tools_logger = logging.getLogger('adev.tools')
main_logger = logging.getLogger('adev.main')

LOG_FORMATS = {
    logging.DEBUG: {'fg': 'white', 'dim': True},
    logging.INFO: {'fg': 'green'},
    logging.WARN: {'fg': 'yellow'},
}
pyg_lexer = Python3TracebackLexer()
pyg_formatter = Terminal256Formatter(style='vim')


class CustomStreamHandler(logging.StreamHandler):
    def setFormatter(self, fmt):
        self.formatter = fmt
        self.formatter.stream_is_tty = isatty and isatty(self.stream)


class DevtoolsFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
        self.stream_is_tty = False

    @staticmethod
    def get_log_format(record):
        return LOG_FORMATS.get(record.levelno, {'fg': 'red'})


class DefaultFormatter(DevtoolsFormatter):
    def format(self, record):
        msg = super().format(record)
        if not self.stream_is_tty:
            return msg
        m = re.match(r'^(\[.*?\])', msg)
        if m:
            time = click.style(m.groups()[0], fg='magenta')
            msg = click.style(msg[m.end():], **self.get_log_format(record))
            return click.style(time + msg)
        else:
            return click.style(msg, **self.get_log_format(record))


# only way to get "extra" from a LogRecord is to look in record.__dict__ and ignore all the standard keys
standard_record_keys = {
    'name',
    'msg',
    'args',
    'levelname',
    'levelno',
    'pathname',
    'filename',
    'module',
    'exc_info',
    'exc_text',
    'stack_info',
    'lineno',
    'funcName',
    'created',
    'msecs',
    'relativeCreated',
    'thread',
    'threadName',
    'processName',
    'process',
    'message',
}


class ErrorFormatter(DevtoolsFormatter):
    def formatMessage(self, record):
        s = super().formatMessage(record)
        extra = {k: v for k, v in record.__dict__.items() if k not in standard_record_keys}
        if extra:
            s += '\nExtra: ' + format_extra(extra, highlight=self.stream_is_tty)
        return s

    def formatException(self, ei):
        sio = StringIO()
        traceback.print_exception(*ei, file=sio)
        stack = sio.getvalue()
        sio.close()
        if self.stream_is_tty and pyg_lexer:
            return pygments.highlight(stack, lexer=pyg_lexer, formatter=pyg_formatter).rstrip('\n')
        else:
            return stack


def log_config(verbose: bool) -> dict:
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
            'aiohttp_access': {
                'format': '%(message)s',
            },
            'aiohttp_server': {
                'format': '%(message)s',
                'class': 'aiohttp_devtools.logs.ErrorFormatter',
            },
        },
        'handlers': {
            'default': {
                'level': log_level,
                'class': 'aiohttp_devtools.logs.CustomStreamHandler',
                'formatter': 'default'
            },
            'no_ts': {
                'level': log_level,
                'class': 'aiohttp_devtools.logs.CustomStreamHandler',
                'formatter': 'no_ts'
            },
            'aiohttp_access': {
                'level': log_level,
                'class': 'logging.StreamHandler',
                'formatter': 'aiohttp_access'
            },
            'aiohttp_server': {
                'level': log_level,
                'class': 'aiohttp_devtools.logs.CustomStreamHandler',
                'formatter': 'aiohttp_server'
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
            },
            'aiohttp.server': {
                'handlers': ['aiohttp_server'],
                'level': log_level,
            },
        },
    }


def setup_logging(verbose):
    config = log_config(verbose)
    logging.config.dictConfig(config)
