import logging
import re

import click

dft_logger = logging.getLogger('adev.runserver.default')
main_access_logger = logging.getLogger('aiohttp.access')
aux_logger = logging.getLogger('dev_server')

LOG_COLOURS = {
    logging.DEBUG: 'white',
    logging.INFO: 'green',
    logging.WARN: 'yellow',
}


class DefaultHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        colour = LOG_COLOURS.get(record.levelno, 'red')
        m = re.match('^(\[.*?\])', log_entry)
        if m:
            time = click.style(m.groups()[0], fg='magenta')
            msg = click.style(log_entry[m.end():], fg=colour)
            click.echo(time + msg)
        else:
            click.secho(log_entry, fg=colour)


class AuxiliaryLogHandler(logging.Handler):
    prefix = click.style('◆', fg='blue')

    def emit(self, record):
        log_entry = self.format(record)
        colour = LOG_COLOURS.get(record.levelno, 'red')
        m = re.match('^(\[.*?\] )', log_entry)
        time = click.style(m.groups()[0], fg='magenta')
        msg = log_entry[m.end():]
        if record.levelno == logging.INFO and msg.startswith('>'):
            msg = '{prefix} {msg}'.format(prefix=self.prefix, msg=msg[2:])
        else:
            msg = click.style(msg, fg=colour)
        click.echo(time + msg)


class MainAccessLogHandler(logging.Handler):
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


def setup_logging(verbose=False):
    log_level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S')

    # for h in dft_logger.handlers:
    #     if isinstance(h, DefaultHandler):
    #         return
    dft_hdl = DefaultHandler()
    dft_hdl.setFormatter(formatter)
    dft_logger.addHandler(dft_hdl)
    dft_logger.setLevel(log_level)

    aux_hdl = AuxiliaryLogHandler()
    aux_hdl.setFormatter(formatter)
    aux_logger.addHandler(aux_hdl)
    aux_logger.setLevel(log_level)

    main_hdl = MainAccessLogHandler()
    main_hdl.setFormatter(formatter)
    main_access_logger.addHandler(main_hdl)
    main_access_logger.setLevel(logging.DEBUG)


def fmt_size(num):
    if num == '':
        return ''
    if num < 1024:
        return '{:0.0f}B'.format(num)
    else:
        return '{:0.1f}KB'.format(num / 1024)
