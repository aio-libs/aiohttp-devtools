import asyncio

from aiohttp import ClientSession
from watchgod import awatch

from ..logs import rs_dft_logger as logger
from .config import Config
from .serve import WS, src_reload, start_main_app


class WatchTask:
    def __init__(self, path: str, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._app = None
        self._task = None
        assert path
        self._awatch = awatch(path)

    async def start(self, app):
        self._app = app
        self._task = self._loop.create_task(self._run())

    async def _run(self):
        raise NotImplementedError()

    async def close(self, *args):
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
        await self._start_dev_server()

        async for changes in self._awatch:
            self._reloads += 1
            if any(f.endswith('.py') for _, f in changes):
                logger.debug('%d changes, restarting server', len(changes))
                await self._stop_dev_server()
                await self._start_dev_server()
                await self._src_reload_when_live()
            elif len(changes) > 1 or any(f.endswith(self.template_files) for _, f in changes):
                await src_reload(self._app)
            else:
                await src_reload(self._app, changes.pop()[1])

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

    async def _start_dev_server(self):
        act = 'Start' if self._reloads == 0 else 'Restart'
        logger.info('%sing dev server at http://%s:%s ●', act, self._config.host, self._config.main_port)
        self._runner = await start_main_app(self._config)

    async def _stop_dev_server(self):
        logger.debug('stopping server process...')
        self._runner and await self._runner.cleanup()

    async def close(self, *args):
        await self._stop_dev_server()
        await super().close()
        await self._session.close()


class LiveReloadTask(WatchTask):
    async def _run(self):
        async for changes in self._awatch:
            if len(changes) > 1:
                await src_reload(self._app)
            else:
                await src_reload(self._app, changes.pop()[1])
