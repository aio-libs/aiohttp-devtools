import os
from pathlib import Path
from pprint import pformat

from multiprocessing import set_start_method
from watchdog.observers import Observer

from ..logs import rs_dft_logger
from .serve import create_auxiliary_app, import_string
from .watch import AllCodeEventHandler, PyCodeEventHandler, LiveReloadEventHandler


def _run_app(app, observer, port):
    loop = app.loop
    handler = app.make_handler(access_log=None)
    srv = loop.run_until_complete(loop.create_server(handler, '0.0.0.0', port))

    try:
        loop.run_forever()
    except KeyboardInterrupt:  # pragma: no branch
        pass
    finally:
        rs_dft_logger.info('shutting down server...')
        close_websockets = loop.create_task(app.close_websockets())
        observer.stop()
        observer.join()
        srv.close()
        loop.run_until_complete(srv.wait_closed())
        loop.run_until_complete(app.shutdown())
        loop.run_until_complete(close_websockets)
        loop.run_until_complete(handler.finish_connections(0.001))
        loop.run_until_complete(app.cleanup())
    loop.close()


def runserver(**config):
    # force a full reload to interpret an updated version of code, this must be called only once
    set_start_method('spawn')

    _, code_path = import_string(config['app_path'], config['app_factory'])
    static_path = config.pop('static_path')
    config.update(
        code_path=str(code_path),
        static_path=static_path and str(Path(static_path).resolve()),
    )
    rs_dft_logger.debug('config:\n%s', pformat(config))

    aux_app = create_auxiliary_app(
        static_path=config['static_path'],
        port=config['aux_port'],
        static_url=config['static_url'],
        livereload=config['livereload'],
    )

    observer = Observer()
    code_event_handler = PyCodeEventHandler(aux_app, config)
    rs_dft_logger.debug('starting PyCodeEventHandler to watch %s', config['code_path'])
    observer.schedule(code_event_handler, config['code_path'], recursive=True)

    all_code_event_handler = AllCodeEventHandler(aux_app)
    observer.schedule(all_code_event_handler, config['code_path'], recursive=True)

    static_path = config['static_path']
    if static_path:
        static_event_handler = LiveReloadEventHandler(aux_app)
        rs_dft_logger.debug('starting LiveReloadEventHandler to watch %s', static_path)
        observer.schedule(static_event_handler, static_path, recursive=True)
    observer.start()

    url = 'http://localhost:{aux_port}'.format(**config)
    rs_dft_logger.info('Starting aux server at %s ◆', url)

    if static_path:
        rel_path = Path(static_path).absolute().relative_to(os.getcwd())
        rs_dft_logger.info('serving static files from ./%s/ at %s%s', rel_path, url, config['static_url'])

    return _run_app(aux_app, observer, config['aux_port'])


def serve_static(*, static_path: str, livereload: bool, port: int):
    rs_dft_logger.debug('Config: path="%s", livereload=%s, port=%s', static_path, livereload, port)

    app = create_auxiliary_app(static_path=static_path, port=port, livereload=livereload)

    observer = Observer()
    if livereload:
        livereload_event_handler = LiveReloadEventHandler(app)
        rs_dft_logger.debug('starting LiveReloadEventHandler to watch %s', static_path)
        observer.schedule(livereload_event_handler, static_path, recursive=True)

    observer.start()

    url = 'http://localhost:{}'.format(port)
    extra = ', livereload ON' if livereload else ''
    rs_dft_logger.info('Serving "%s" at %s%s', static_path, url, extra)
    return _run_app(app, observer, port),
