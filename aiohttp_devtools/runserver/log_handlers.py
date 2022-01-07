import json
import warnings
from datetime import datetime, timedelta
from typing import Dict, Optional, Union, cast

from aiohttp import web
from aiohttp.abc import AbstractAccessLogger

dbtb = '/_debugtoolbar/'
check = '?_checking_alive=1'


class _AccessLogger(AbstractAccessLogger):
    prefix: str

    def get_msg(self, request: web.BaseRequest, response: web.StreamResponse, time: float) -> Optional[str]:
        raise NotImplementedError()

    def extra(self, request: web.BaseRequest, response: web.StreamResponse, time: float) -> Optional[Dict[str, object]]:
        pass

    def log(self, request: web.BaseRequest, response: web.StreamResponse, time: float) -> None:
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

    def get_msg(self, request: web.BaseRequest, response: web.StreamResponse, time: float) -> str:
        return '{method} {path} {code} {size} {ms:0.0f}ms'.format(
            method=request.method,
            path=request.path_qs,
            code=response.status,
            size=fmt_size(response.body_length),
            ms=time * 1000,
        )

    def extra(self, request: web.BaseRequest, response: web.StreamResponse, time: float) -> Optional[Dict[str, object]]:
        if response.status <= 310:
            return None

        request_body = request._read_bytes
        body_text = response.text if isinstance(response, web.Response) else None
        details = {
            "request_duration_ms": round(time * 1000, 3),
            "request_headers": dict(request.headers),
            "request_body": parse_body(request_body, "request body"),
            "request_size": fmt_size(0 if request_body is None else len(request_body)),
            "response_headers": dict(response.headers),
            "response_body": parse_body(body_text, "response body"),
        }
        return {"details": details}


class AuxAccessLogger(_AccessLogger):
    prefix = '◆'

    def get_msg(self, request: web.BaseRequest, response: web.StreamResponse, time: float) -> Optional[str]:
        # don't log livereload
        if request.path in {"/livereload", "/livereload.js"}:
            return None

        return "{method} {path} {code} {size}".format(
            method=request.method,
            path=request.path_qs,
            code=response.status,
            size=fmt_size(response.body_length),
        )


def fmt_size(num: int) -> str:
    if not num:
        return ''
    if num < 1024:
        return '{:0.0f}B'.format(num)
    else:
        return '{:0.1f}KB'.format(num / 1024)


def parse_body(v: Union[str, bytes, None], name: str) -> object:
    if v is None:
        return v

    try:
        return json.loads(v)
    except UnicodeDecodeError:
        v = cast(bytes, v)  # UnicodeDecodeError only occurs on bytes.
        warnings.warn("UnicodeDecodeError parsing " + name, UserWarning)
        # bytes which cause UnicodeDecodeError can cause problems later on
        return v.decode(errors="ignore")
    except (ValueError, TypeError):
        return v
