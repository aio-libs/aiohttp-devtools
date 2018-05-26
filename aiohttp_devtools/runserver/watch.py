import asyncio
import os
import signal
import sys
from multiprocessing import Process

from aiohttp import ClientSession
from watchgod import awatch

from ..exceptions import AiohttpDevException
from ..logs import rs_dft_logger as logger
from .config import Config
from .serve import WS, serve_main_app, src_reload


class WatchTask:
    def __init__(self, path: str, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._app = None
        self._task = None
        assert path
        self.stopper = asyncio.Event(loop=self._loop)
        self._awatch = awatch(path, stop_event=self.stopper)

    async def start(self, app):
        self._app = app
        self._task = self._loop.create_task(self._run())

    async def _run(self):
        raise NotImplementedError()

    async def close(self, *args):
        if self._task:
            self.stopper.set()
            async with self._awatch.lock:
                if self._task.done():
                    self._task.result()
                self._task.cancel()


class AppTask(WatchTask):
    template_files = '.html', '.jinja', '.jinja2'

    def __init__(self, config: Config, loop: asyncio.AbstractEventLoop):
        self._config = config
        self._reloads = 0
        self._session = ClientSession(loop=loop)
        self._runner = None
        super().__init__(self._config.code_directory, loop)

    async def _run(self):
        try:
            self._start_dev_server()

            async for changes in self._awatch:
                self._reloads += 1
                if any(f.endswith('.py') for _, f in changes):
                    logger.debug('%d changes, restarting server', len(changes))
                    self._stop_dev_server()
                    self._start_dev_server()
                    await self._src_reload_when_live()
                elif len(changes) > 1 or any(f.endswith(self.template_files) for _, f in changes):
                    # reload all pages
                    await src_reload(self._app)
                else:
                    # a single (non template) file has changed, reload a single file.
                    await src_reload(self._app, changes.pop()[1])
        except Exception as exc:
            logger.exception(exc)
            await self._session.close()
            raise AiohttpDevException('error running dev server')

    async def _src_reload_when_live(self, checks=20):
        if self._app[WS]:
            url = 'http://localhost:{.main_port}/?_checking_alive=1'.format(self._config)
            logger.debug('checking app at "%s" is running before prompting reload...', url)
            for i in range(checks):
                await asyncio.sleep(0.1, loop=self._app.loop)
                try:
                    async with self._session.get(url):
                        pass
                except OSError as e:
                    logger.debug('try %d | OSError %d app not running', i, e.errno)
                else:
                    logger.debug('try %d | app running, reloading...', i)
                    await src_reload(self._app)
                    return

    def _start_dev_server(self):
        act = 'Start' if self._reloads == 0 else 'Restart'
        logger.info('%sing dev server at http://%s:%s ●', act, self._config.host, self._config.main_port)

        try:
            tty_path = os.ttyname(sys.stdin.fileno())
        except OSError:  # pragma: no branch
            # fileno() always fails with pytest
            tty_path = '/dev/tty'
        except AttributeError:
            # on windows, without a windows machine I've no idea what else to do here
            tty_path = None

        self._process = Process(target=serve_main_app, args=(self._config, tty_path))
        self._process.start()

    def _stop_dev_server(self):
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
            logger.warning('server process already dead, exit code: %s', self._process.exitcode)

    async def close(self, *args):
        self.stopper.set()
        self._stop_dev_server()
        await asyncio.gather(super().close(), self._session.close())


class LiveReloadTask(WatchTask):
    async def _run(self):
        async for changes in self._awatch:
            if len(changes) > 1:
                await src_reload(self._app)
            else:
                await src_reload(self._app, changes.pop()[1])
