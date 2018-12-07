import logging
import re
from datetime import datetime, timedelta

import click
from aiohttp.abc import AbstractAccessLogger

from ..logs import get_log_format


class AuxiliaryHandler(logging.Handler):
    prefix = click.style('◆', fg='blue')

    def emit(self, record):
        log_entry = self.format(record)
        m = re.match(r'^(\[.*?\] )', log_entry)
        time = click.style(m.groups()[0], fg='magenta')
        msg = log_entry[m.end():]
        if record.levelno in {logging.INFO, logging.DEBUG} and msg.startswith('>'):
            if msg.endswith(' 304 0B'):
                msg = '{} {}'.format(self.prefix, click.style(msg[2:], dim=True))
            else:
                msg = '{} {}'.format(self.prefix, msg[2:])
        else:
            msg = click.style(msg, **get_log_format(record))
        click.echo(time + msg)


dbtb = '/_debugtoolbar/'
check = '?_checking_alive=1'


class AccessLogger(AbstractAccessLogger):
    prefix = click.style('●', fg='blue')

    def log(self, request, response, time):
        now = datetime.now()
        start_time = now - timedelta(seconds=time)
        time_str = click.style(start_time.strftime('[%H:%M:%S]'), fg='magenta')

        path = request.path
        msg = '{method} {path} {code} {size} {ms:0.0f}ms'.format(
            method=request.method,
            path=path,
            code=response.status,
            size=fmt_size(response.body_length),
            ms=time * 1000,
        )
        if (response.status, response.body_length) == ('304', 0) or path.startswith(dbtb) or path.endswith(check):
            msg = click.style(msg, dim=True)
        msg = '{} {}'.format(self.prefix, msg)
        self.logger.info(time_str + msg)


def fmt_size(num):
    if not num:
        return ''
    if num < 1024:
        return '{:0.0f}B'.format(num)
    else:
        return '{:0.1f}KB'.format(num / 1024)
