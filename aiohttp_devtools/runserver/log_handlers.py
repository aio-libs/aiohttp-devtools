import logging
import re

import click

from ..logs import LOG_COLOURS


class AuxiliaryHandler(logging.Handler):
    prefix = click.style('◆', fg='blue')

    def emit(self, record):
        log_entry = self.format(record)
        colour = LOG_COLOURS.get(record.levelno, 'red')
        m = re.match('^(\[.*?\] )', log_entry)
        time = click.style(m.groups()[0], fg='magenta')
        msg = log_entry[m.end():]
        if record.levelno in {logging.INFO, logging.DEBUG} and msg.startswith('>'):
            if msg.endswith(' 304 0B'):
                msg = '{} {}'.format(self.prefix, click.style(msg[2:], dim=True))
            else:
                msg = '{} {}'.format(self.prefix, msg[2:])
        else:
            msg = click.style(msg, fg=colour)
        click.echo(time + msg)


class AiohttpAccessHandler(logging.Handler):
    prefix = click.style('●', fg='blue')

    def emit(self, record):
        log_entry = self.format(record)
        m = re.match('^(\[.*?\] )', log_entry)
        time = click.style(m.groups()[0], fg='magenta')
        msg = log_entry[m.end():]
        method, path, _, code, size = msg.split(' ')
        size = fmt_size(int(size))
        msg = '{prefix} {method} {path} {code} {size}'.format(prefix=self.prefix, method=method, path=path,
                                                              code=code, size=size)
        click.echo(time + msg)


def fmt_size(num):
    if num == '':
        return ''
    if num < 1024:
        return '{:0.0f}B'.format(num)
    else:
        return '{:0.1f}KB'.format(num / 1024)
