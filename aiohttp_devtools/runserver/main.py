import asyncio
import contextlib
import os
from multiprocessing import set_start_method

from ..logs import rs_dft_logger as logger
from .config import Config
from .serve import HOST, check_port_open, create_auxiliary_app
from .watch import AppTask, LiveReloadTask


def run_app(app, port, loop):
    handler = app.make_handler(access_log=None, loop=loop)

    loop.run_until_complete(app.startup())
    server = loop.run_until_complete(loop.create_server(handler, HOST, port))

    try:
        loop.run_forever()
    except KeyboardInterrupt:  # pragma: no branch
        pass
    finally:
        logger.info('shutting down server...')
        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.run_until_complete(app.shutdown())
        with contextlib.suppress(asyncio.TimeoutError, KeyboardInterrupt):
            loop.run_until_complete(handler.shutdown(0.1))
        with contextlib.suppress(asyncio.TimeoutError, KeyboardInterrupt):
            loop.run_until_complete(app.cleanup())
        with contextlib.suppress(KeyboardInterrupt):
            loop.close()


def runserver(**config_kwargs):
    """
    Prepare app ready to run development server.

    :param config_kwargs: see config.Config for more details
    :return: tuple (auxiliary app, auxiliary app port, event loop)
    """
    # force a full reload in sub processes so they load an updated version of code, this must be called only once
    set_start_method('spawn')

    config = Config(**config_kwargs)
    config.check()
    loop = asyncio.get_event_loop()

    loop.run_until_complete(check_port_open(config.main_port, loop))

    aux_app = create_auxiliary_app(
        static_path=config.static_path_str,
        static_url=config.static_url,
        livereload=config.livereload,
    )

    main_manager = AppTask(config, loop)
    aux_app.on_startup.append(main_manager.start)
    aux_app.on_shutdown.append(main_manager.close)

    if config.static_path:
        static_manager = LiveReloadTask(config.static_path_str, loop)
        logger.debug('starting livereload to watch %s', config.static_path_str)
        aux_app.on_startup.append(static_manager.start)
        aux_app.on_shutdown.append(static_manager.close)

    url = 'http://{0.host}:{0.aux_port}'.format(config)
    logger.info('Starting aux server at %s ◆', url)

    if config.static_path:
        rel_path = config.static_path.relative_to(os.getcwd())
        logger.info('serving static files from ./%s/ at %s%s', rel_path, url, config.static_url)

    return aux_app, config.aux_port, loop


def serve_static(*, static_path: str, livereload: bool=True, port: int=8000):
    logger.debug('Config: path="%s", livereload=%s, port=%s', static_path, livereload, port)

    loop = asyncio.get_event_loop()
    app = create_auxiliary_app(static_path=static_path, livereload=livereload)

    if livereload:
        livereload_manager = LiveReloadTask(static_path, loop)
        logger.debug('starting livereload to watch %s', static_path)
        app.on_startup.append(livereload_manager.start)
        app.on_shutdown.append(livereload_manager.close)

    livereload_status = 'ON' if livereload else 'OFF'
    logger.info('Serving "%s" at http://localhost:%d, livereload %s', static_path, port, livereload_status)
    return app, port, loop
