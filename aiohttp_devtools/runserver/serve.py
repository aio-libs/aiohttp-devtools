import asyncio
import json
import mimetypes
import os
import sys
from importlib import import_module
from pathlib import Path

import aiohttp_debugtoolbar
from aiohttp import FileSender
from aiohttp import MsgType, web
from aiohttp.hdrs import LAST_MODIFIED, CONTENT_ENCODING
from aiohttp.web_exceptions import HTTPNotFound, HTTPNotModified
from aiohttp.web_urldispatcher import StaticRoute

from .logs import aux_logger, fmt_size, setup_logging

LIVE_RELOAD_SNIPPET = b'\n<script src="%s/livereload.js"></script>\n'
JINJA_ENV = 'aiohttp_jinja2_environment'


def modify_main_app(app, **config):
    aux_server = 'http://localhost:{aux_port}'.format(**config)
    livereload_enabled = config['livereload']
    aux_logger.debug('livereload enabled: %s', '✓' if livereload_enabled else '✖')
    if livereload_enabled:
        livereload_snippet = LIVE_RELOAD_SNIPPET % aux_server.encode()
        async def on_prepare(request, response):
            if not request.path.startswith('/_debugtoolbar') and 'text/html' in response.content_type:
                if hasattr(response, 'body'):
                    response.body += livereload_snippet
        app.on_response_prepare.append(on_prepare)

    static_url = '{}/{}'.format(aux_server, config['static_url'].strip('/'))
    app['static_root_url'] = static_url
    aux_logger.debug('global environment variable static_url="%s" added to app as "static_root_url"', static_url)

    if config['debug_toolbar']:
        aiohttp_debugtoolbar.setup(app)


def serve_main_app(**config):
    setup_logging(config['verbose'])
    app_factory, _ = import_string(config['app_path'], config['app_factory'])

    loop = asyncio.new_event_loop()
    app = app_factory(loop=loop)

    if app is None:
        raise TypeError('"app" may not be none')

    modify_main_app(app, **config)
    handler = app.make_handler(access_log_format='%r %s %b')
    srv = loop.run_until_complete(loop.create_server(handler, '0.0.0.0', config['main_port']))

    try:
        loop.run_forever()
    except KeyboardInterrupt:  # pragma: no branch
        pass
    finally:
        srv.close()
        loop.run_until_complete(srv.wait_closed())
        loop.run_until_complete(app.shutdown())
        loop.run_until_complete(handler.finish_connections(4))
        loop.run_until_complete(app.cleanup())
    loop.close()


WS = 'websockets'


class AuxiliaryApplication(web.Application):
    def static_reload(self, change_path):
        static_root = self['static_path']
        change_path = Path(change_path).relative_to(static_root)

        path = Path(self['static_url']) / change_path
        self._broadcast_change(path=str(path))

    def src_reload(self):
        self._broadcast_change()

    def _broadcast_change(self, path=None):
        cli_count = len(self[WS])
        if cli_count == 0:
            return
        s = '' if cli_count == 1 else 's'
        aux_logger.info('prompting reload of %s on %d client%s', path or 'page', cli_count, s)
        for ws, url in self[WS]:
            data = {
                'command': 'reload',
                'path': path or url,
                'liveCSS': True,
                'liveImg': True,
            }
            try:
                ws.send_str(json.dumps(data))
            except RuntimeError as e:
                # "RuntimeError: websocket connection is closing" occurs if content type changes due to code change
                aux_logger.error(str(e))

    async def close_websockets(self):
        aux_logger.debug('closing %d websockets...', len(self[WS]))
        coros = [ws.close() for ws, _ in self[WS]]
        await asyncio.gather(*coros, loop=self._loop)


def create_auxiliary_app(*, static_path, port, static_url='/', livereload=True, loop=None):
    loop = loop or asyncio.new_event_loop()
    app = AuxiliaryApplication(loop=loop)
    app[WS] = []
    app.update(
        static_path=static_path,
        static_url=static_url,
    )

    if livereload:
        app.router.add_route('GET', '/livereload.js', livereload_js)
        app.router.add_route('GET', '/livereload', websocket_handler)
        server_address = 'http://localhost:{}'.format(port)
        livereload_snippet = LIVE_RELOAD_SNIPPET % server_address.encode()
        aux_logger.debug('enabling livereload on static app')
    else:
        livereload_snippet = None

    if static_path:
        route = CustomStaticRoute('static-router', static_url, static_path + '/', livereload_snippet=livereload_snippet)
        app.router.register_route(route)

    return app


async def livereload_js(request):
    if request.if_modified_since:
        aux_logger.debug('> %s %s %s 0B', request.method, request.path, 304)
        raise HTTPNotModified()

    script_key = 'livereload_script'
    lr_script = request.app.get(script_key)
    if lr_script is None:
        lr_path = Path(__file__).absolute().parent.joinpath('livereload.js')
        with lr_path.open('rb') as f:
            lr_script = f.read()
            request.app[script_key] = lr_script

    aux_logger.debug('> %s %s %s %s', request.method, request.path, 200, fmt_size(len(lr_script)))
    return web.Response(body=lr_script, content_type='application/javascript',
                        headers={LAST_MODIFIED: 'Fri, 01 Jan 2016 00:00:00 GMT'})


async def websocket_handler(request):
    ws = web.WebSocketResponse()
    url = None
    await ws.prepare(request)
    ws_type_lookup = {k.value: v for v, k in MsgType.__members__.items()}

    async for msg in ws:
        if msg.tp == MsgType.text:
            try:
                data = json.loads(msg.data)
            except json.JSONDecodeError as e:
                aux_logger.error('JSON decode error: %s', str(e))
            else:
                command = data['command']
                if command == 'hello':
                    if 'http://livereload.com/protocols/official-7' not in data['protocols']:
                        aux_logger.error('live reload protocol 7 not supported by client %s', msg.data)
                        ws.close()
                    else:
                        handshake = {
                            'command': 'hello',
                            'protocols': [
                                'http://livereload.com/protocols/official-7',
                            ],
                            'serverName': 'livereload-aiohttp',
                        }
                        ws.send_str(json.dumps(handshake))
                elif command == 'info':
                    aux_logger.debug('browser connected: %s', data)
                    url = data['url'].split('/', 3)[-1]
                    request.app[WS].append((ws, url))
                else:
                    aux_logger.error('Unknown ws message %s', msg.data)
        elif msg.tp == MsgType.error:
            aux_logger.error('ws connection closed with exception %s',  ws.exception())
        else:
            aux_logger.error('unknown websocket message type %s, data: %s', ws_type_lookup[msg.tp], msg.data)

    aux_logger.debug('browser disconnected')
    if url:
        request.app[WS].remove((ws, url))
    return ws


class CustomFileSender(FileSender):
    def __init__(self, *args, **kwargs):
        self.lr_snippet = kwargs.pop('livereload_snippet')
        self.lr_snippet_len = len(self.lr_snippet)
        super().__init__(*args, **kwargs)

    async def send(self, request, filepath):
        """
        Send filepath to client using request.

        As with super except:
        * adds lr_snippet_length to content_length and writes lr_snippet to the tail of the response.
        """

        ct, encoding = mimetypes.guess_type(str(filepath))
        if not ct:
            ct = 'application/octet-stream'
        is_html = ct == 'text/html'

        st = filepath.stat()
        modsince = request.if_modified_since
        if not is_html and modsince is not None and st.st_mtime <= modsince.timestamp():
            raise HTTPNotModified()

        resp = self._response_factory()
        resp.content_type = ct
        if encoding:
            resp.headers[CONTENT_ENCODING] = encoding
        resp.last_modified = st.st_mtime

        file_size = st.st_size
        resp.content_length = file_size + self.lr_snippet_len if is_html else file_size
        resp.set_tcp_cork(True)
        try:
            with filepath.open('rb') as f:
                await self._sendfile_fallback(request, resp, f, file_size)
            if is_html:
                resp.write(self.lr_snippet)
                await resp.drain()
        finally:
            resp.set_tcp_nodelay(True)

        return resp


class CustomStaticRoute(StaticRoute):
    def __init__(self, *args, **kwargs):
        self._asset_path = None  # TODO
        livereload_snippet = kwargs.pop('livereload_snippet')
        super().__init__(*args, **kwargs)
        self._show_index = True
        if livereload_snippet:
            self._file_sender = CustomFileSender(resp_factory=self._file_sender._response_factory,
                                                 chunk_size=self._file_sender._chunk_size,
                                                 livereload_snippet=livereload_snippet)

    async def handle(self, request):
        filename = request.match_info['filename']
        raw_path = self._directory.joinpath(filename)
        try:
            filepath = raw_path.resolve()
            filepath.relative_to(self._directory)
        except FileNotFoundError:
            try:
                html_file = raw_path.with_name(raw_path.name + '.html').resolve().relative_to(self._directory)
            except (FileNotFoundError, ValueError):
                pass
            else:
                request.match_info['filename'] = str(html_file)
        except ValueError:
            pass
        else:
            if filepath.is_dir():
                index_file = filepath / 'index.html'
                if index_file.exists():
                    request.match_info['filename'] = str(index_file.relative_to(self._directory))

        status, length = 'unknown', ''
        try:
            response = await super().handle(request)
        except HTTPNotModified:
            status, length = 304, 0
            raise
        except HTTPNotFound:
            _404_msg = '404: Not Found\n\n' + _get_asset_content(self._asset_path)
            response = web.Response(body=_404_msg.encode(), status=404, content_type='text/plain')
            status, length = response.status, response.content_length
        else:
            status, length = response.status, response.content_length
        finally:
            l = aux_logger.info if status in {200, 304} else aux_logger.warning
            l('> %s %s %s %s', request.method, request.path, status, fmt_size(length))
        return response


def _get_asset_content(asset_path):
    if not asset_path:
        return ''
    with asset_path.open() as f:
        return 'Asset file contents:\n\n{}'.format(f.read())


APP_FACTORY_NAMES = [
    'app',
    'app_factory',
    'get_app',
    'create_app',
]


def import_string(file_path, attr_name=None, _trying_again=False):
    """
    Import attribute/class from from a python module. Raise ImportError if the import failed.

    Approximately stolen from django.

    :param file_path: path to python module
    :param attr_name: attribute to get from module
    :return: (attribute, Path object for directory of file)
    """

    module_path = file_path.replace('.py', '').replace('/', '.')

    try:
        module = import_module(module_path)
    except ImportError:
        if _trying_again:
            raise
        # add current working directory to pythonpath and try again
        p = os.getcwd()
        aux_logger.debug('adding current working director %s to pythonpath and reattempting import', p)
        sys.path.append(p)
        return import_string(file_path, attr_name, True)

    if attr_name is None:
        try:
            attr_name = next(an for an in APP_FACTORY_NAMES if hasattr(module, an))
        except StopIteration as e:
            raise ImportError('No name supplied and no default app factory found in "%s"' % module_path) from e
        else:
            aux_logger.debug('found default attribute "%s" in module "%s"' % (attr_name, module))

    try:
        attr = getattr(module, attr_name)
    except AttributeError as e:
        raise ImportError('Module "%s" does not define a "%s" attribute/class' % (module_path, attr_name)) from e

    directory = Path(module.__file__).parent
    return attr, directory
