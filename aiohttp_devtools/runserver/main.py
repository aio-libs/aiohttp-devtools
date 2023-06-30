import asyncio
import os
from multiprocessing import set_start_method
from typing import Any, Type, TypedDict

from aiohttp.abc import AbstractAccessLogger
from aiohttp.web import Application

from ..logs import rs_dft_logger as logger
from .config import Config
from .log_handlers import AuxAccessLogger
from .serve import HOST, check_port_open, create_auxiliary_app
from .watch import AppTask, LiveReloadTask


class RunServer(TypedDict):
    app: Application
    host: str
    port: int
    shutdown_timeout: float
    access_log_class: Type[AbstractAccessLogger]


def runserver(**config_kwargs: Any) -> RunServer:
    """Prepare app ready to run development server.

    :param config_kwargs: see config.Config for more details
    :return: tuple (auxiliary app, auxiliary app port, event loop)
    """
    # force a full reload in sub processes so they load an updated version of code, this must be called only once
    set_start_method('spawn')

    config = Config(**config_kwargs)
    config.import_app_factory()

    asyncio.run(check_port_open(config.main_port))

    aux_app = create_auxiliary_app(
        static_path=config.static_path_str,
        static_url=config.static_url,
        livereload=config.livereload,
    )

    main_manager = AppTask(config)
    aux_app.cleanup_ctx.append(main_manager.cleanup_ctx)

    if config.static_path:
        static_manager = LiveReloadTask(config.static_path)
        logger.debug('starting livereload to watch %s', config.static_path_str)
        aux_app.cleanup_ctx.append(static_manager.cleanup_ctx)

    url = 'http://{0.host}:{0.aux_port}'.format(config)
    logger.info('Starting aux server at %s ◆', url)

    if config.static_path:
        rel_path = config.static_path.relative_to(os.getcwd())
        logger.info('serving static files from ./%s/ at %s%s', rel_path, url, config.static_url)

    return {"app": aux_app, "host": HOST, "port": config.aux_port,
            "shutdown_timeout": 0.01, "access_log_class": AuxAccessLogger}


def serve_static(*, static_path: str, livereload: bool = True, port: int = 8000,
                 browser_cache: bool = False) -> RunServer:
    logger.debug('Config: path="%s", livereload=%s, port=%s', static_path, livereload, port)

    app = create_auxiliary_app(static_path=static_path, livereload=livereload,
                               browser_cache=browser_cache)

    if livereload:
        livereload_manager = LiveReloadTask(static_path)
        logger.debug('starting livereload to watch %s', static_path)
        app.cleanup_ctx.append(livereload_manager.cleanup_ctx)

    livereload_status = 'ON' if livereload else 'OFF'
    logger.info('Serving "%s" at http://localhost:%d, livereload %s', static_path, port, livereload_status)
    return {"app": app, "host": HOST, "port": port,
            "shutdown_timeout": 0.01, "access_log_class": AuxAccessLogger}
