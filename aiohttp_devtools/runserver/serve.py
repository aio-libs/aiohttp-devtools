import asyncio
import json
import os
import sys
from importlib import import_module
from pathlib import Path

from aiohttp import MsgType, web
from aiohttp.hdrs import LAST_MODIFIED
from aiohttp.web_exceptions import HTTPNotFound, HTTPNotModified
from aiohttp.web_urldispatcher import StaticRoute

from .logs import aux_logger, fmt_size, setup_logging

LIVE_RELOAD_SNIPPET = b'\n<script src="%s/livereload.js"></script>\n'
JINJA_ENV = 'aiohttp_jinja2_environment'


def modify_main_app(app, **config):
    aux_server = 'http://localhost:{aux_port}'.format(**config)
    live_reload_snippet = LIVE_RELOAD_SNIPPET % aux_server.encode()
    livereload_enabled = config['livereload']
    aux_logger.debug('livereload enabled: %s', '✓' if livereload_enabled else '✖')

    if JINJA_ENV in app:
        static_url = '{}/{}'.format(aux_server, config['static_url'].strip('/'))
        # if a jinja environment is setup add a global variable `static_url`
        # which can be used as in `src="{{ static_url }}/foobar.css"`
        app[JINJA_ENV].globals['static_url'] = static_url
        aux_logger.debug('global environment variable static_url="%s" added to jinja environment', static_url)

    async def on_prepare(request, response):
        if livereload_enabled and 'text/html' in response.content_type:
            response.body += live_reload_snippet
    app.on_response_prepare.append(on_prepare)


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
        config = self['config']
        static_root = config['static_path']
        change_path = Path(change_path).relative_to(static_root)

        path = Path(config['static_url']) / change_path
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
        for ws, _ in self[WS]:
            await ws.close()


def create_auxiliary_app(*, loop=None, **config):
    loop = loop or asyncio.new_event_loop()
    app = AuxiliaryApplication(loop=loop)
    app[WS] = []
    app['config'] = config

    app.router.add_route('GET', '/livereload.js', livereload_js)
    app.router.add_route('GET', '/livereload', websocket_handler)

    static_path = config['static_path']
    if static_path:
        static_root = static_path + '/'
        app.router.register_route(CustomStaticRoute('static-router', config['static_url'], static_root))
    return app


async def livereload_js(request):
    if request.if_modified_since:
        aux_logger.debug('> %s %s %s 0', request.method, request.path, 304)
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


class CustomStaticRoute(StaticRoute):
    def __init__(self, *args, **kwargs):
        self._asset_path = None  # TODO
        super().__init__(*args, **kwargs)

    async def handle(self, request):
        filename = request.match_info['filename']
        try:
            filepath = self._directory.joinpath(filename).resolve()
        except (ValueError, FileNotFoundError, OSError):
            pass
        else:
            if filepath.is_dir():
                request.match_info['filename'] = str(filepath.joinpath('index.html').relative_to(self._directory))
        status, length = 'unknown', ''
        try:
            response = await super().handle(request)
        except HTTPNotModified:
            status, length = 304, 0
            raise
        except HTTPNotFound:
            _404_msg = '404: Not Found\n\n' + _get_asset_content(self._asset_path)
            response = web.Response(body=_404_msg.encode(), status=404)
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
