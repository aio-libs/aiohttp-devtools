import asyncio
import os
from pathlib import Path
from typing import Any, TypedDict

from aiohttp.abc import AbstractAccessLogger
from aiohttp.web import Application

from ..logs import rs_dft_logger as logger
from .config import Config
from .log_handlers import AuxAccessLogger
from .serve import check_port_open, create_auxiliary_app
from .watch import AppTask, LiveReloadTask
from ssl import SSLContext


class RunServer(TypedDict):
    app: Application
    host: str
    port: int
    shutdown_timeout: float
    access_log_class: type[AbstractAccessLogger]
    ssl_context: SSLContext | None


def runserver(**config_kwargs: Any) -> RunServer:
    """Prepare app ready to run development server.

    :param config_kwargs: see config.Config for more details
    :return: tuple (auxiliary app, auxiliary app port, event loop)
    """
    config = Config(**config_kwargs)
    module = config.import_module()
    ssl_context = config.get_ssl_context(module)

    asyncio.run(check_port_open(config.main_port, host=config.bind_address))

    aux_app = create_auxiliary_app(
        static_path=config.static_path_str,
        static_url=config.static_url,
        livereload=config.livereload,
    )

    main_manager = AppTask(config)
    aux_app.cleanup_ctx.append(main_manager.cleanup_ctx)

    assert config.watch_path
    # AppTask also reloads the static files which are inside the path that it watches,
    # so watching them a second time would prompt every reload twice.
    if config.static_path and not config.static_path.is_relative_to(config.watch_path):
        static_manager = LiveReloadTask(config.static_path)
        logger.debug('starting livereload to watch %s', config.static_path_str)
        aux_app.cleanup_ctx.append(static_manager.cleanup_ctx)

    url = f'{config.protocol}://{config.host}:{config.aux_port}'
    logger.info('Starting aux server at %s ◆', url)

    if config.static_path:
        rel_path = config.static_path.relative_to(os.getcwd())
        logger.info('serving static files from ./%s/ at %s%s', rel_path, url, config.static_url)

    return {"app": aux_app, "host": config.bind_address, "port": config.aux_port,
            "shutdown_timeout": 0.01, "access_log_class": AuxAccessLogger, "ssl_context": ssl_context}


def serve_static(*, static_path: str, livereload: bool = True, bind_address: str = "localhost", port: int = 8000,
                 browser_cache: bool = False) -> RunServer:
    logger.debug('Config: path="%s", livereload=%s, port=%s', static_path, livereload, port)

    resolved_path = str(Path(static_path).resolve())
    app = create_auxiliary_app(static_path=resolved_path, livereload=livereload,
                               browser_cache=browser_cache)

    if livereload:
        livereload_manager = LiveReloadTask(resolved_path)
        logger.debug('starting livereload to watch %s', resolved_path)
        app.cleanup_ctx.append(livereload_manager.cleanup_ctx)

    livereload_status = 'ON' if livereload else 'OFF'
    logger.info('Serving "%s" at http://%s:%d, livereload %s', static_path, bind_address, port, livereload_status)
    return {"app": app, "host": bind_address, "port": port,
            "shutdown_timeout": 0.01, "access_log_class": AuxAccessLogger, "ssl_context": None}
