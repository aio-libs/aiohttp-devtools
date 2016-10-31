import asyncio
import os
from multiprocessing import set_start_method
from pathlib import Path

from aiohttp.web import Application
from trafaret_config import ConfigError
from watchdog.observers import Observer

from ..logs import rs_dft_logger as logger
from .serve import create_auxiliary_app, import_string
from .watch import AllCodeEventHandler, LiveReloadEventHandler, PyCodeEventHandler


class BadSetup(Exception):
    pass


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
        raise BadSetup('Configuration Error: {}'.format(e)) from e
    if not isinstance(app, Application):
        raise BadSetup('app factory returns "{}" not an aiohttp.web.Application'.format(type(app)))
    loop.run_until_complete(app.startup())


def runserver(*,
              app_path: str,
              app_factory: str=None,
              static_path: str=None,
              static_url: str='/static/',
              livereload: bool=True,
              debug_toolbar: bool=True,
              main_port: int=8000,
              aux_port: int=8001,
              verbose: bool=False,
              loop: asyncio.AbstractEventLoop=None):
    # force a full reload to interpret an updated version of code, this must be called only once
    set_start_method('spawn')

    _app_factory, code_path = import_string(app_path, app_factory)
    check_app_factory(_app_factory)

    code_path = str(code_path)
    static_path = static_path and str(Path(static_path).resolve())

    aux_app = create_auxiliary_app(
        static_path=static_path,
        port=aux_port,
        static_url=static_url,
        livereload=livereload,
        loop=loop,
    )

    observer = Observer()

    config_dict = dict(
        app_path=app_path,
        app_factory=app_factory,
        static_url=static_url,
        livereload=livereload,
        debug_toolbar=debug_toolbar,
        main_port=main_port,
        aux_port=aux_port,
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
        observer.schedule(static_event_handler, static_path, recursive=True)
    observer.start()

    url = 'http://localhost:{}'.format(aux_port)
    logger.info('Starting aux server at %s ◆', url)

    if static_path:
        rel_path = Path(static_path).absolute().relative_to(os.getcwd())
        logger.info('serving static files from ./%s/ at %s%s', rel_path, url, static_url)

    return aux_app, observer, aux_port


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
