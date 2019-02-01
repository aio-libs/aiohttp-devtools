import json
import warnings
from datetime import datetime, timedelta

from aiohttp.abc import AbstractAccessLogger

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
        pqs = request.path_qs
        # log messages are encoded to JSON, so they can be easily coloured or not by the logger which knows whether
        # the stream "isatty"
        msg = json.dumps({
            'time': start_time.strftime('[%H:%M:%S]'),
            'prefix': self.prefix,
            'msg': msg,
            'dim': (response.status, response.body_length) == (304, 0) or pqs.startswith(dbtb) or pqs.endswith(check)
        })
        self.logger.info(msg, extra=self.extra(request, response, time))


class AccessLogger(_AccessLogger):
    prefix = '●'

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
            details = dict(
                request_duration_ms=round(time * 1000, 3),
                request_headers=dict(request.headers),
                request_body=parse_body(request_body, 'request body'),
                request_size=fmt_size(0 if request_body is None else len(request_body)),
                response_headers=dict(response.headers),
                response_body=parse_body(response.text or response.body, 'response body'),
            )
            return dict(details=details)


class AuxAccessLogger(_AccessLogger):
    prefix = '◆'

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
        except UnicodeDecodeError:
            warnings.warn('UnicodeDecodeError parsing ' + name, UserWarning)
            # bytes which cause UnicodeDecodeError can cause problems later on
            return v.decode(errors='ignore')
        except (ValueError, TypeError):
            pass
    return v
