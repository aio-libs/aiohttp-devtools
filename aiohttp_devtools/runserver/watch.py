import asyncio
import os
import signal
from datetime import datetime
from multiprocessing import Process

from aiohttp import ClientSession
from aiohttp.web import Application
from watchdog.events import PatternMatchingEventHandler, match_any_paths, unicode_paths

from ..logs import rs_dft_logger as logger
from .config import Config
from .serve import WS, serve_main_app

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
        raise NotImplementedError()


class PyCodeEventHandler(BaseEventHandler):
    patterns = ['*.py']

    def __init__(self, app: Application, config: Config, loop: asyncio.AbstractEventLoop):
        self._app = app
        self._config = config
        self._loop = loop
        super().__init__()
        self._start_process()

    def on_event(self, event):
        logger.debug('%s | %0.3f seconds since last change, restarting server', event, self._since_change)
        self.stop_process()
        self._start_process()
        self._loop.create_task(self.src_reload_when_live())

    async def src_reload_when_live(self, checks=20):
        if not self._app[WS]:
            return
        url = 'http://localhost:{.main_port}/?_checking_alive=1'.format(self._config)
        logger.debug('checking app at "%s" is running before prompting reload...', url)
        async with ClientSession(loop=self._app.loop) as session:
            for i in range(checks):
                await asyncio.sleep(0.1, loop=self._app.loop)
                try:
                    async with session.get(url):
                        pass
                except OSError as e:
                    logger.debug('try %d | OSError %d app not running', i, e.errno)
                else:
                    logger.debug('try %d | app running, reloading...', i)
                    return self._app.src_reload()

    def _start_process(self):
        act = 'Start' if self._change_count == 0 else 'Restart'
        logger.info('%sing dev server at http://localhost:%s ●', act, self._config.main_port)

        self._process = Process(target=serve_main_app, args=(self._config,))
        self._process.start()

    def stop_process(self):
        if self._process.is_alive():
            logger.debug('stopping server process...')
            os.kill(self._process.pid, signal.SIGINT)
            self._process.join(5)
            if self._process.exitcode is None:
                logger.warning('process has not terminated, sending SIGKILL')
                os.kill(self._process.pid, signal.SIGKILL)
                self._process.join(1)
            else:
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
