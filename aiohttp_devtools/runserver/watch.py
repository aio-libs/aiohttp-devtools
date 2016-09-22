import os
import signal
from datetime import datetime
from multiprocessing import Process, set_start_method

from watchdog.events import PatternMatchingEventHandler, match_any_paths, unicode_paths

from .logs import MainAccessLogHandler, dft_logger
from .serve import serve_main_app

# specific to jetbrains I think, very annoying if not ignored
JB_BACKUP_FILE = '*___jb_???___'

# force a full reload to interpret an updated version of code:
set_start_method('spawn')


class _BaseEventHandler(PatternMatchingEventHandler):
    patterns = ['*.*']
    ignore_directories = True
    ignore_patterns = [
        '*/.git/*',
        '*/.idea/*',
        # next two in case a virtualenv directory is included in watched path
        '*/include/python*',
        '*/lib/python*',
        '*/aiohttp_devserver/*',
        JB_BACKUP_FILE,
    ]

    def __init__(self, aux_app, config, *args, **kwargs):
        self._app = aux_app
        self._config = config

        self._change_dt = datetime.now()
        self._since_change = None
        self._change_count = 0
        super().__init__(*args, **kwargs)

    def dispatch(self, event):

        if event.is_directory:
            return

        paths = []
        if getattr(event, 'dest_path', None) is not None:
            paths.append(unicode_paths.decode(event.dest_path))
        if event.src_path:
            paths.append(unicode_paths.decode(event.src_path))

        if match_any_paths(paths, included_patterns=[JB_BACKUP_FILE]):
            # special case for these fields if either path matches skip
            return

        if not match_any_paths(paths, included_patterns=self.patterns, excluded_patterns=self.ignore_patterns):
            return

        self._since_change = (datetime.now() - self._change_dt).total_seconds()
        if self._since_change <= 1:
            dft_logger.debug('%s | %0.3f seconds since last build, skipping', event, self._since_change)
            return

        self._change_dt = datetime.now()
        self._change_count += 1
        self.on_event(event)

    def on_event(self, event):
        pass


class CodeFileEventHandler(_BaseEventHandler):
    patterns = ['*.py']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._start_process()

    def on_event(self, event):
        dft_logger.debug('%s | %0.3f seconds since last change, restarting server', event, self._since_change)
        self.stop_process()
        self._start_process()

    def _start_process(self):
        if self._change_count == 0:
            p = MainAccessLogHandler.prefix
            dft_logger.info('Starting dev server at http://localhost:%s %s', self._config['main_port'], p)
        else:
            dft_logger.info('Restarting dev server at http://localhost:%s', self._config['main_port'])

        self._process = Process(target=serve_main_app, kwargs=self._config)
        self._process.start()

    def stop_process(self):
        if self._process.is_alive():
            dft_logger.debug('stopping server process...')
            os.kill(self._process.pid, signal.SIGINT)
            self._process.join(5)
            dft_logger.debug('process stopped')
        else:
            dft_logger.warning('server process already dead, exit code: %d', self._process.exitcode)


class AllCodeEventEventHandler(_BaseEventHandler):
    patterns = [
        '*.py',
        '*.html',
        '*.jinja',
        '*.jinja2',
    ]

    def on_event(self, event):
        self._app.src_reload()


class StaticFileEventEventHandler(_BaseEventHandler):
    def on_event(self, event):
        self._app.static_reload(event.src_path)
