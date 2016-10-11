import os
import signal
from datetime import datetime
from multiprocessing import Process

from watchdog.events import PatternMatchingEventHandler, match_any_paths, unicode_paths

from ..logs import rs_dft_logger as logger
from ..tools.sass_generator import SassGenerator
from .serve import serve_main_app

# specific to jetbrains I think, very annoying if not completely ignored
JB_BACKUP_FILE = '*___jb_???___'


class BaseEventHandler(PatternMatchingEventHandler):
    patterns = ['*.*']
    ignore_directories = True
    # ignore a few common directories some shouldn't be in watched directories anyway,
    # but excluding them makes any mis-configured watch less painful
    ignore_patterns = [
        '*/.git/*',              # git
        '*/.idea/*',             # pycharm / jetbrains
        JB_BACKUP_FILE,          # pycharm / jetbrains
        '*/include/python*',     # in virtualenv
        '*/lib/python*',         # in virtualenv
        '*/aiohttp_devtools/*',  # itself
        '*~',                    # linux temporary file
        '*.sw?',                 # vim temporary file
    ]
    skipped_event = False

    def __init__(self, *args, **kwargs):
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
            logger.debug('%s | %0.3f seconds since last build, skipping', event, self._since_change)
            self.skipped_event = True
            return

        self._change_dt = datetime.now()
        self._change_count += 1
        self.on_event(event)
        self.skipped_event = False

    def on_event(self, event):
        pass


class PyCodeEventHandler(BaseEventHandler):
    patterns = ['*.py']

    def __init__(self, app, config):
        self._app = app
        self._config = config
        super().__init__()
        self._start_process()

    def on_event(self, event):
        logger.debug('%s | %0.3f seconds since last change, restarting server', event, self._since_change)
        self.stop_process()
        self._start_process()

    def _start_process(self):
        if self._change_count == 0:
            logger.info('Starting dev server at http://localhost:%s ●', self._config['main_port'])
        else:
            logger.info('Restarting dev server at http://localhost:%s ●', self._config['main_port'])

        self._process = Process(target=serve_main_app, kwargs=self._config)
        self._process.start()

    def stop_process(self):
        if self._process.is_alive():
            logger.debug('stopping server process...')
            os.kill(self._process.pid, signal.SIGINT)
            self._process.join(5)
            logger.debug('process stopped')
        else:
            logger.warning('server process already dead, exit code: %d', self._process.exitcode)


class AllCodeEventHandler(BaseEventHandler):
    patterns = [
        '*.html',
        '*.jinja',
        '*.jinja2',
    ]

    def __init__(self, app):
        self._app = app
        super().__init__()

    def on_event(self, event):
        self._app.src_reload()


class LiveReloadEventHandler(BaseEventHandler):
    ignore_directories = False

    def __init__(self, app):
        self._app = app
        super().__init__()

    def on_event(self, event):
        self._app.src_reload(None if self.skipped_event else event.src_path)


class SassEventHandler(BaseEventHandler):
    patterns = [
        '*.s?ss',
        '*.css',
    ]

    def __init__(self, input_dir: str, output_dir: str):
        self.sass_gen = SassGenerator(input_dir, output_dir, True)
        super().__init__()
        self.sass_gen.build()

    def on_event(self, event):
        self.sass_gen.build()
