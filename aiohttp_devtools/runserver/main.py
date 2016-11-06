import asyncio
import os
from multiprocessing import set_start_method

from aiohttp.web import Application
from trafaret_config import ConfigError
from watchdog.observers import Observer

from ..exceptions import AiohttpDevConfigError
from ..logs import rs_dft_logger as logger
from .load import find_app_path, import_string, load_settings_file
from .serve import create_auxiliary_app
from .watch import AllCodeEventHandler, LiveReloadEventHandler, PyCodeEventHandler


def run_app(app, observer, port):
    loop = app.loop
    handler = app.make_handler(access_log=None)
    server = loop.run_until_complete(loop.create_server(handler, '0.0.0.0', port))

    try:
        loop.run_forever()
    except KeyboardInterrupt:  # pragma: no branch
        pass
    finally:
        logger.info('shutting down server...')
        observer.stop()
        observer.join()
        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.run_until_complete(app.shutdown())
        loop.run_until_complete(app.cleanup())
        loop.run_until_complete(handler.finish_connections(0.001))
    loop.close()


def check_app_factory(app_factory):
    """
    run the app factory as a very basic check it's working and returns the right thing, this should cat config errors.
    :param app_factory: app_factory coroutine
    :return:
    """
    logger.debug('checking app factory "{}"'.format(app_factory))
    loop = asyncio.new_event_loop()
    try:
        app = app_factory(loop)
    except ConfigError as e:
        raise AiohttpDevConfigError('Configuration Error: {}'.format(e)) from e
    if not isinstance(app, Application):
        raise AiohttpDevConfigError('app factory returns "{}" not an aiohttp.web.Application'.format(type(app)))
    loop.run_until_complete(app.startup())


def runserver(*, app_path: str, verbose: bool=False, loop: asyncio.AbstractEventLoop=None, **kwargs):
    # force a full reload to interpret an updated version of code, this must be called only once
    set_start_method('spawn')
    valid_app_path = find_app_path(app_path)
    config = load_settings_file(valid_app_path, **kwargs)

    logger.debug('config as loaded from key word arguments and possible yaml file:')
    for k, v in config.items():
        logger.debug('  %s: %r', k, v)

    _app_factory, code_path = import_string(config['app_path'], config['app_factory'])
    check_app_factory(_app_factory)

    code_path = str(code_path)
    static_path = config['static_path']

    aux_app = create_auxiliary_app(
        static_path=static_path and str(static_path),
        port=config['aux_port'],
        static_url=config['static_url'],
        livereload=config['livereload'],
        loop=loop,
    )

    observer = Observer()

    config_dict = dict(
        app_path=config['app_path'],
        static_url=config['static_url'],
        livereload=config['livereload'],
        debug_toolbar=config['debug_toolbar'],
        app_factory=config['app_factory'],
        main_port=config['main_port'],
        aux_port=config['aux_port'],
        verbose=verbose,
    )

    # PyCodeEventHandler takes care of running and restarting the main app
    code_event_handler = PyCodeEventHandler(aux_app, config_dict)
    logger.debug('starting PyCodeEventHandler to watch %s', code_path)
    observer.schedule(code_event_handler, code_path, recursive=True)

    all_code_event_handler = AllCodeEventHandler(aux_app)
    observer.schedule(all_code_event_handler, code_path, recursive=True)

    if static_path:
        static_event_handler = LiveReloadEventHandler(aux_app)
        logger.debug('starting LiveReloadEventHandler to watch %s', static_path)
        observer.schedule(static_event_handler, static_path and str(static_path), recursive=True)
    observer.start()

    url = 'http://localhost:{aux_port}'.format(**config)
    logger.info('Starting aux server at %s ◆', url)

    if static_path:
        rel_path = static_path.relative_to(os.getcwd())
        logger.info('serving static files from ./%s/ at %s%s', rel_path, url, config['static_url'])

    return aux_app, observer, config['aux_port']


def serve_static(*, static_path: str, livereload: bool=True, port: int=8000, loop: asyncio.AbstractEventLoop=None):
    logger.debug('Config: path="%s", livereload=%s, port=%s', static_path, livereload, port)

    app = create_auxiliary_app(static_path=static_path, port=port, livereload=livereload, loop=loop)

    observer = Observer()
    if livereload:
        livereload_event_handler = LiveReloadEventHandler(app)
        logger.debug('starting LiveReloadEventHandler to watch %s', static_path)
        observer.schedule(livereload_event_handler, static_path, recursive=True)

    observer.start()

    logger.info('Serving "%s" at http://localhost:%d, livereload %s', static_path, port, 'ON' if livereload else 'OFF')
    return app, observer, port
