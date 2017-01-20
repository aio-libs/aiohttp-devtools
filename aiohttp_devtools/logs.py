import logging
import logging.config
import re

import click

rs_dft_logger = logging.getLogger('adev.server.dft')
rs_aux_logger = logging.getLogger('adev.server.aux')

tools_logger = logging.getLogger('adev.tools')
main_logger = logging.getLogger('adev.main')

LOG_FORMATS = {
    logging.DEBUG: {'fg': 'white', 'dim': True},
    logging.INFO: {'fg': 'green'},
    logging.WARN: {'fg': 'yellow'},
}


def get_log_format(record):
    return LOG_FORMATS.get(record.levelno, {'fg': 'red'})


class DefaultHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        m = re.match('^(\[.*?\])', log_entry)
        if m:
            time = click.style(m.groups()[0], fg='magenta')
            msg = click.style(log_entry[m.end():], **get_log_format(record))
            click.echo(time + msg)
        else:
            click.secho(log_entry, **get_log_format(record))


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
            },
            'no_ts': {
                'format': '%(message)s'
            },
        },
        'handlers': {
            'default': {
                'level': log_level,
                'class': 'aiohttp_devtools.logs.DefaultHandler',
                'formatter': 'default'
            },
            'no_ts': {
                'level': log_level,
                'class': 'aiohttp_devtools.logs.DefaultHandler',
                'formatter': 'no_ts'
            },
            'rs_aux': {
                'level': log_level,
                'class': 'aiohttp_devtools.runserver.log_handlers.AuxiliaryHandler',
                'formatter': 'default'
            },
            'aiohttp_access': {
                'level': log_level,
                'class': 'aiohttp_devtools.runserver.log_handlers.AiohttpAccessHandler',
                'formatter': 'default'
            },
        },
        'loggers': {
            rs_dft_logger.name: {
                'handlers': ['default'],
                'level': log_level,
            },
            rs_aux_logger.name: {
                'handlers': ['rs_aux'],
                'level': log_level,
            },
            'aiohttp.access': {
                'handlers': ['aiohttp_access'],
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
        },
    }


def setup_logging(verbose):
    config = log_config(verbose)
    logging.config.dictConfig(config)
