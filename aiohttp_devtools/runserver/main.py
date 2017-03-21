import asyncio
import os
from multiprocessing import set_start_method

from watchdog.observers import Observer

from ..logs import rs_dft_logger as logger
from .config import Config
from .serve import HOST, check_port_open, create_auxiliary_app
from .watch import AllCodeEventHandler, LiveReloadEventHandler, PyCodeEventHandler


def run_app(app, observer, port, loop):
    handler = app.make_handler(access_log=None, loop=loop)
    server = loop.run_until_complete(loop.create_server(handler, HOST, port))

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
        try:
            loop.run_until_complete(handler.finish_connections(0.1))
        except asyncio.TimeoutError:
            pass
    loop.close()


def runserver(*, loop: asyncio.AbstractEventLoop=None, **config_kwargs):
    """
    Prepare app and observer ready to run development server.

    :param loop: asyncio loop to use
    :param config_kwargs: see config.Config for more details
    :return: tuple (auxiliary app, observer, auxiliary app port, event loop)
    """

    # force a full reload to interpret an updated version of code, this must be called only once
    set_start_method('spawn')
    loop = loop or asyncio.get_event_loop()

    config = Config(**config_kwargs)
    logger.debug('config as loaded from key word arguments and (possibly) yaml file:\n%s', config)

    config.check(loop)
    loop.run_until_complete(check_port_open(config.main_port, loop))

    aux_app = create_auxiliary_app(
        static_path=config.static_path_str,
        port=config.aux_port,
        static_url=config.static_url,
        livereload=config.livereload,
    )

    observer = Observer()

    # PyCodeEventHandler takes care of running and restarting the main app
    code_event_handler = PyCodeEventHandler(aux_app, config, loop)
    logger.debug('starting PyCodeEventHandler to watch %s', config.code_directory)
    observer.schedule(code_event_handler, config.code_directory_str, recursive=True)

    all_code_event_handler = AllCodeEventHandler(aux_app)
    observer.schedule(all_code_event_handler, config.code_directory_str, recursive=True)

    if config.static_path:
        static_event_handler = LiveReloadEventHandler(aux_app)
        logger.debug('starting LiveReloadEventHandler to watch %s', config.static_path_str)
        observer.schedule(static_event_handler, config.static_path_str, recursive=True)
    observer.start()

    url = 'http://localhost:{.aux_port}'.format(config)
    logger.info('Starting aux server at %s ◆', url)

    if config.static_path:
        rel_path = config.static_path.relative_to(os.getcwd())
        logger.info('serving static files from ./%s/ at %s%s', rel_path, url, config.static_url)

    return aux_app, observer, config.aux_port, loop


def serve_static(*, static_path: str, livereload: bool=True, port: int=8000, loop: asyncio.AbstractEventLoop=None):
    logger.debug('Config: path="%s", livereload=%s, port=%s', static_path, livereload, port)

    loop = loop or asyncio.get_event_loop()
    app = create_auxiliary_app(static_path=static_path, port=port, livereload=livereload)

    observer = Observer()
    if livereload:
        livereload_event_handler = LiveReloadEventHandler(app)
        logger.debug('starting LiveReloadEventHandler to watch %s', static_path)
        observer.schedule(livereload_event_handler, static_path, recursive=True)

    observer.start()

    logger.info('Serving "%s" at http://localhost:%d, livereload %s', static_path, port, 'ON' if livereload else 'OFF')
    return app, observer, port, loop
