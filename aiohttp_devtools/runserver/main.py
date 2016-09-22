import os
from pathlib import Path
from pprint import pformat

from watchdog.observers import Observer

from .logs import AuxiliaryLogHandler, dft_logger
from .serve import create_auxiliary_app, import_string
from .watch import AllCodeEventEventHandler, CodeFileEventHandler, StaticFileEventEventHandler


def run_apps(**config):
    _, code_path = import_string(config['app_path'], config['app_factory'])
    static_path = config.pop('static_path')
    config.update(
        code_path=str(code_path),
        static_path=static_path and str(Path(static_path).resolve()),
    )
    dft_logger.debug('config:\n%s', pformat(config))

    aux_app = create_auxiliary_app(**config)

    observer = Observer()
    code_file_eh = CodeFileEventHandler(aux_app, config)
    dft_logger.debug('starting CodeFileEventHandler to watch %s', config['code_path'])
    observer.schedule(code_file_eh, config['code_path'], recursive=True)

    all_code_file_eh = AllCodeEventEventHandler(aux_app, config)
    observer.schedule(all_code_file_eh, config['code_path'], recursive=True)

    static_path = config['static_path']
    if static_path:
        static_file_eh = StaticFileEventEventHandler(aux_app, config)
        dft_logger.debug('starting StaticFileEventEventHandler to watch %s', static_path)
        observer.schedule(static_file_eh, static_path, recursive=True)
    observer.start()

    loop = aux_app.loop
    handler = aux_app.make_handler(access_log=None)
    srv = loop.run_until_complete(loop.create_server(handler, '0.0.0.0', config['aux_port']))

    url = 'http://localhost:{aux_port}'.format(**config)
    dft_logger.info('Starting aux server at %s %s', url, AuxiliaryLogHandler.prefix)

    static_path = config['static_path']
    if static_path:
        rel_path = Path(static_path).absolute().relative_to(os.getcwd())
        dft_logger.info('serving static files from ./%s/ at %s%s', rel_path, url, config['static_url'])

    try:
        loop.run_forever()
    except KeyboardInterrupt:  # pragma: no branch
        pass
    finally:
        dft_logger.debug('shutting down auxiliary server...')
        loop.create_task(aux_app.close_websockets())
        observer.stop()
        observer.join()
        srv.close()
        loop.run_until_complete(srv.wait_closed())
        loop.run_until_complete(aux_app.shutdown())
        loop.run_until_complete(handler.finish_connections(2))
        loop.run_until_complete(aux_app.cleanup())
    loop.close()
