import asyncio
import os
import signal
import sys
import time
from contextlib import suppress
from multiprocessing import Process
from pathlib import Path
from typing import AsyncIterator, Iterable, Optional, Tuple, Union

from aiohttp import ClientSession, web
from aiohttp.client_exceptions import ClientError, ClientConnectionError
from watchfiles import awatch

from ..exceptions import AiohttpDevException
from ..logs import rs_dft_logger as logger
from .config import Config
from .serve import LAST_RELOAD, STATIC_PATH, WS, serve_main_app, src_reload


class WatchTask:
    _app: web.Application
    _task: "asyncio.Task[None]"

    def __init__(self, path: Union[Path, str]):
        self._path = path

    async def start(self, app: web.Application) -> None:
        self._app = app
        self.stopper = asyncio.Event()
        self._awatch = awatch(self._path, stop_event=self.stopper, step=250)
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        raise NotImplementedError()

    async def close(self, *args: object) -> None:
        if self._task:
            self.stopper.set()
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def cleanup_ctx(self, app: web.Application) -> AsyncIterator[None]:
        await self.start(app)
        yield
        await self.close(app)


class AppTask(WatchTask):
    template_files = '.html', '.jinja', '.jinja2'

    def __init__(self, config: Config):
        self._config = config
        self._reloads = 0
        self._session: Optional[ClientSession] = None
        self._runner = None
        assert self._config.watch_path
        super().__init__(self._config.watch_path)

    async def _run(self, live_checks: int = 150) -> None:
        assert self._app is not None

        self._session = ClientSession()
        try:
            self._start_dev_server()

            static_path = self._app[STATIC_PATH]

            def is_static(changes: Iterable[Tuple[object, str]]) -> bool:
                return all(str(c[1]).startswith(static_path) for c in changes)

            async for changes in self._awatch:
                self._reloads += 1
                logger.debug("file changes: %s", changes)
                if any(f.endswith('.py') for _, f in changes):
                    logger.debug('%d changes, restarting server', len(changes))

                    count, t = self._app[LAST_RELOAD]
                    if len(self._app[WS]) < count:
                        wait_delay = max(t + 5 - time.time(), 0)
                        logger.debug("waiting upto %s seconds before restarting", wait_delay)

                        for i in range(int(wait_delay / 0.1)):
                            await asyncio.sleep(0.1)
                            if len(self._app[WS]) >= count:
                                break

                    await self._stop_dev_server()
                    self._start_dev_server()
                    await self._src_reload_when_live(live_checks)
                    # Pause to allow the browser to reload and reconnect. This avoids
                    # multiple changes causing the app to restart before WS reconnection.
                    await asyncio.sleep(1)
                elif len(changes) == 1 and is_static(changes):
                    # a single (static) file has changed, reload a single file.
                    await src_reload(self._app, changes.pop()[1])
                else:
                    # reload all pages
                    await src_reload(self._app)
        except Exception as exc:
            logger.exception(exc)
            await self._session.close()
            raise AiohttpDevException('error running dev server')

    async def _src_reload_when_live(self, checks: int) -> None:
        assert self._app is not None and self._session is not None

        if self._app[WS]:
            url = 'http://localhost:{.main_port}/?_checking_alive=1'.format(self._config)
            logger.debug('checking app at "%s" is running before prompting reload...', url)
            for i in range(checks):
                await asyncio.sleep(0.1)
                try:
                    async with self._session.get(url):
                        pass
                except OSError as e:
                    logger.debug('try %d | OSError %d app not running', i, e.errno)
                else:
                    logger.debug('try %d | app running, reloading...', i)
                    await src_reload(self._app)
                    return

    def _start_dev_server(self) -> None:
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

    async def _stop_dev_server(self) -> None:
        if self._process.is_alive():
            logger.debug('stopping server process...')
            if self._config.shutdown_by_url:  # Workaround for signals not working on Windows
                url = "http://localhost:{}{}/shutdown".format(self._config.main_port, self._config.path_prefix)
                logger.debug("Attempting to stop process via shutdown endpoint {}".format(url))
                try:
                    with suppress(ClientConnectionError):
                        async with ClientSession() as session:
                            async with session.get(url):
                                pass
                except (ConnectionError, ClientError, asyncio.TimeoutError) as ex:
                    if self._process.is_alive():
                        msg = "shutdown endpoint caused an error (will try signals next)"
                        logger.warning(msg.format(type(ex), ex), exc_info=True)
                    else:
                        msg = "process stopped (despite error at shutdown endpoint)"
                        logger.warning(msg.format(type(ex), ex), exc_info=True)
                        return
                else:
                    self._process.join(5)
                    if self._process.exitcode is None:
                        logger.warning("shutdown endpoint did not terminate process, trying signals")
                    else:
                        logger.debug("process stopped via shutdown endpoint")
                        return
            if self._process.pid:
                logger.debug("sending SIGINT")
                os.kill(self._process.pid, signal.SIGINT)
            self._process.join(5)
            if self._process.exitcode is None:
                logger.warning('process has not terminated, sending SIGKILL')
                self._process.kill()
                self._process.join(1)
            else:
                logger.debug('process stopped')
        else:
            logger.warning('server process already dead, exit code: %s', self._process.exitcode)

    async def close(self, *args: object) -> None:
        self.stopper.set()
        await self._stop_dev_server()
        if self._session is None:
            raise RuntimeError("Object not started correctly before calling .close()")
        await asyncio.gather(super().close(), self._session.close())


class LiveReloadTask(WatchTask):
    async def _run(self) -> None:
        async for changes in self._awatch:
            if len(changes) > 1:
                await src_reload(self._app)
            else:
                await src_reload(self._app, changes.pop()[1])
