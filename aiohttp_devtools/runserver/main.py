import asyncio
import contextlib
import os
from multiprocessing import set_start_method

from aiohttp.web_runner import AppRunner, TCPSite

from ..logs import rs_dft_logger as logger
from .config import Config
from .log_handlers import AuxAccessLogger
from .serve import HOST, check_port_open, create_auxiliary_app
from .watch import AppTask, LiveReloadTask


def runserver(**config_kwargs):
    """
    Prepare app ready to run development server.

    :param config_kwargs: see config.Config for more details
    :return: tuple (auxiliary app, auxiliary app port, event loop)
    """
    # force a full reload in sub processes so they load an updated version of code, this must be called only once
    set_start_method('spawn')

    config = Config(**config_kwargs)
    config.import_app_factory()
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
        static_manager = LiveReloadTask(config.static_path, loop)
        logger.debug('starting livereload to watch %s', config.static_path_str)
        aux_app.on_startup.append(static_manager.start)
        aux_app.on_shutdown.append(static_manager.close)

    url = 'http://{0.host}:{0.aux_port}'.format(config)
    logger.info('Starting aux server at %s ◆', url)

    if config.static_path:
        rel_path = config.static_path.relative_to(os.getcwd())
        logger.info('serving static files from ./%s/ at %s%s', rel_path, url, config.static_url)

    return {"app": aux_app, "port": config.aux_port, "access_log_class": AuxAccessLogger}


def serve_static(*, static_path: str, livereload: bool = True, port: int = 8000):
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
    return {"app": app, "port": port, "access_log_class": AuxAccessLogger}
