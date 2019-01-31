import json
import warnings
from datetime import datetime, timedelta

from aiohttp.abc import AbstractAccessLogger
from devtools import sformat

dbtb = '/_debugtoolbar/'
check = '?_checking_alive=1'


class _AccessLogger(AbstractAccessLogger):
    prefix = NotImplemented

    def get_msg(self, request, response, time):
        raise NotImplementedError()

    def extra(self, request, response, time):
        pass

    def log(self, request, response, time):
        msg = self.get_msg(request, response, time)
        if not msg:
            return
        now = datetime.now()
        start_time = now - timedelta(seconds=time)
        time_str = sformat(start_time.strftime('[%H:%M:%S]'), sformat.magenta)

        path = request.path_qs
        if (response.status, response.body_length) == (304, 0) or path.startswith(dbtb) or path.endswith(check):
            msg = sformat(msg, sformat.dim)
        msg = '{} {}'.format(self.prefix, msg)
        self.logger.info(time_str + msg, extra=self.extra(request, response, time))


class AccessLogger(_AccessLogger):
    prefix = sformat('●', sformat.blue)

    def get_msg(self, request, response, time):
        return '{method} {path} {code} {size} {ms:0.0f}ms'.format(
            method=request.method,
            path=request.path_qs,
            code=response.status,
            size=fmt_size(response.body_length),
            ms=time * 1000,
        )

    def extra(self, request, response, time: float):
        if response.status > 310:
            request_body = request._read_bytes
            return dict(
                request=dict(
                    duration_ms=round(time * 1000, 3),
                    url=str(request.rel_url),
                    method=request.method,
                    host=request.host,
                    headers=dict(request.headers),
                    body=parse_body(request_body, 'request body'),
                    size=fmt_size(0 if request_body is None else len(request_body)),
                ),
                response=dict(
                    status=response.status,
                    headers=dict(response.headers),
                    body=parse_body(response.text or response.body, 'response body'),
                    size=fmt_size(response.body_length),
                ),
            )


class AuxAccessLogger(_AccessLogger):
    prefix = sformat('◆', sformat.blue)

    def get_msg(self, request, response, time):
        # don't log livereload
        if request.path not in {'/livereload', '/livereload.js'}:
            return '{method} {path} {code} {size}'.format(
                method=request.method,
                path=request.path_qs,
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


def parse_body(v, name):
    if isinstance(v, (str, bytes)):
        try:
            return json.loads(v)
        except (ValueError, TypeError):
            pass
        except UnicodeDecodeError:
            warnings.warn('UnicodeDecodeError parsing ' + name, UserWarning)
            # bytes which cause UnicodeDecodeError can cause problems later on
            return v.decode(errors='ignore')
    return v
