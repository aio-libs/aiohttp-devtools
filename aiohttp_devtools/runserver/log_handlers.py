from datetime import datetime, timedelta

import click
from aiohttp.abc import AbstractAccessLogger


dbtb = '/_debugtoolbar/'
check = '?_checking_alive=1'


class _AccessLogger(AbstractAccessLogger):
    prefix = NotImplemented

    def get_msg(self, request, response, time):
        raise NotImplementedError()

    def log(self, request, response, time):
        msg = self.get_msg(request, response, time)
        if not msg:
            return
        now = datetime.now()
        start_time = now - timedelta(seconds=time)
        time_str = click.style(start_time.strftime('[%H:%M:%S]'), fg='magenta')

        path = request.path
        if (response.status, response.body_length) == ('304', 0) or path.startswith(dbtb) or path.endswith(check):
            msg = click.style(msg, dim=True)
        msg = '{} {}'.format(self.prefix, msg)
        self.logger.info(time_str + msg)


class AccessLogger(_AccessLogger):
    prefix = click.style('●', fg='blue')

    def get_msg(self, request, response, time):
        return '{method} {path} {code} {size} {ms:0.0f}ms'.format(
            method=request.method,
            path=request.path,
            code=response.status,
            size=fmt_size(response.body_length),
            ms=time * 1000,
        )


class AuxAccessLogger(_AccessLogger):
    prefix = click.style('◆', fg='blue')

    def get_msg(self, request, response, time):
        path = request.path
        # don't log livereload
        if path not in {'/livereload', '/livereload.js'}:
            return '{method} {path} {code} {size}'.format(
                method=request.method,
                path=path,
                code=response.status,
                size=fmt_size(response.body_length),
            )


def fmt_size(num):
    if not num:
        return ''
    if num < 1024:
        return '{:0.0f}B'.format(num)
    else:
        return '{:0.1f}KB'.format(num / 1024)
