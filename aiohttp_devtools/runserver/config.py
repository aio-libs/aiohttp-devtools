import asyncio
import re
import sys
from importlib import import_module
from pathlib import Path
from typing import Awaitable, Callable, Optional, Union, Literal
from types import ModuleType

from aiohttp import web
from ssl import SSLContext

import __main__
from ..exceptions import AiohttpDevConfigError as AdevConfigError
from ..logs import rs_dft_logger as logger

AppFactory = Union[web.Application, Callable[[], web.Application], Callable[[], Awaitable[web.Application]]]

STD_FILE_NAMES = [
    re.compile(r'main\.py'),
    re.compile(r'app\.py'),
]


APP_FACTORY_NAMES = [
    'app',
    'app_factory',
    'get_app',
    'create_app',
]

DEFAULT_PORT = 8000

INFER_HOST = '<inference>'


class Config:
    def __init__(self, *,
                 app_path: str = '.',
                 root_path: Optional[str] = None,
                 verbose: bool = False,
                 static_path: Optional[str] = None,
                 python_path: Optional[str] = None,
                 static_url: str = '/static/',
                 livereload: bool = True,
                 shutdown_by_url: bool = sys.platform.startswith("win32"),
                 path_prefix: str = "/_devtools",
                 app_factory_name: Optional[str] = None,
                 host: str = INFER_HOST,
                 bind_address: str = "localhost",
                 main_port: Optional[int] = None,
                 aux_port: Optional[int] = None,
                 browser_cache: bool = False,
                 ssl_context_factory_name: Optional[str] = None):
        if root_path:
            self.root_path = Path(root_path).resolve()
            logger.debug('Root path specified: %s', self.root_path)
            self.watch_path: Optional[Path] = self.root_path
        else:
            logger.debug('Root path not specified, using current working directory')
            self.root_path = Path('.').resolve()
            self.watch_path = None

        self.app_path = self._find_app_path(app_path)
        if not self.app_path.name.endswith('.py'):
            raise AdevConfigError('Unexpected extension for app_path: %s, should be .py' % self.app_path.name)
        self.verbose = verbose
        self.settings_found = False

        self.py_file = self._resolve_path(str(self.app_path), 'is_file', 'app-path')
        if python_path:
            self.python_path = self._resolve_path(python_path, "is_dir", "python-path")
        else:
            self.python_path = self.root_path

        self.static_path = self._resolve_path(static_path, "is_dir", "static-path") if static_path else None
        self.static_url = static_url
        self.livereload = livereload
        self.shutdown_by_url = shutdown_by_url
        self.path_prefix = path_prefix
        self.app_factory_name = app_factory_name
        self.infer_host = host == INFER_HOST

        if not self.infer_host:
            self.host = host
        elif bind_address == "0.0.0.0":
            self.host = "localhost"
        else:
            self.host = bind_address

        self.bind_address = bind_address
        if main_port is None:
            main_port = DEFAULT_PORT if ssl_context_factory_name is None else DEFAULT_PORT + 443
        self.main_port = main_port
        if aux_port is None:
            aux_port = main_port + 1 if ssl_context_factory_name is None else DEFAULT_PORT + 1
        self.aux_port = aux_port
        self.browser_cache = browser_cache
        self.ssl_context_factory_name = ssl_context_factory_name
        logger.debug('config loaded:\n%s', self)

    @property
    def protocol(self) -> Literal["http", "https"]:
        return "http" if self.ssl_context_factory_name is None else "https"

    @property
    def static_path_str(self) -> Optional[str]:
        return str(self.static_path) if self.static_path else None

    def _find_app_path(self, app_path: str) -> Path:
        # for backwards compatibility try this first
        path = (self.root_path / app_path).resolve()
        if not path.exists():
            path = Path(app_path).resolve()
        if path.is_file():
            logger.debug('app_path is a file, returning it directly')
            return path

        assert path.is_dir(), 'app_path {} is not a directory'.format(path)
        files = [x for x in path.iterdir() if x.is_file()]
        for std_file_name in STD_FILE_NAMES:
            try:
                file_path = next(f for f in files if std_file_name.fullmatch(f.name))
            except StopIteration:
                pass
            else:
                logger.debug('app_path is a directory with a recognised file %s', file_path)
                return file_path
        raise AdevConfigError('unable to find a recognised default file ("app.py" or "main.py") '
                              'in the directory "%s"' % app_path)

    def _resolve_path(self, _path: str, check: str, arg_name: str) -> Path:
        if _path.startswith('/'):
            path = Path(_path)
            error_msg = '{arg_name} "{path}" is not a valid path'
        else:
            path = Path(self.root_path / _path)
            error_msg = '{arg_name} "{path}" is not a valid path relative to {root}'

        try:
            path = path.resolve()
        except OSError as e:
            raise AdevConfigError(error_msg.format(arg_name=arg_name, path=_path, root=self.root_path)) from e

        if check == 'is_file':
            if not path.is_file():
                raise AdevConfigError('{} is not a file'.format(path))
        else:
            assert check == 'is_dir'
            if not path.is_dir():
                raise AdevConfigError('{} is not a directory'.format(path))
        return path

    def import_module(self) -> ModuleType:
        """Import and return python module.

        Raises:
            AdevConfigError - If the import failed.
        """
        rel_py_file = self.py_file.relative_to(self.python_path)
        module_path = '.'.join(rel_py_file.with_suffix('').parts)
        sys.path.insert(0, str(self.python_path))
        module = import_module(module_path)
        # Rewrite the package name, so it will appear the same as running the app.
        if module.__package__:
            __main__.__package__ = module.__package__

        logger.debug('successfully loaded "%s" from "%s"', module_path, self.python_path)

        self.watch_path = self.watch_path or Path(module.__file__ or ".").parent
        return module

    def get_app_factory(self, module: ModuleType) -> AppFactory:
        """Return attribute/class from a python module.

        Raises:
            AdevConfigError - If the import failed.
        """

        if self.app_factory_name is None:
            try:
                self.app_factory_name = next(an for an in APP_FACTORY_NAMES if hasattr(module, an))
            except StopIteration as e:
                raise AdevConfigError('No name supplied and no default app factory '
                                      'found in {s.py_file.name}'.format(s=self)) from e
            else:
                logger.debug('found default attribute "%s" in module "%s"',
                             self.app_factory_name, module)

        try:
            attr = getattr(module, self.app_factory_name)
        except AttributeError:
            raise AdevConfigError("Module '{}' does not define a '{}' attribute/class".format(
                self.py_file.name, self.app_factory_name))

        if not isinstance(attr, web.Application) and not callable(attr):
            raise AdevConfigError("'{}.{}' is not an Application or callable".format(
                self.py_file.name, self.app_factory_name))

        if hasattr(attr, "__code__"):
            required_args = attr.__code__.co_argcount - len(attr.__defaults__ or ())
            if required_args > 0:
                raise AdevConfigError("'{}.{}' should not have required arguments.".format(
                    self.py_file.name, self.app_factory_name))

        return attr  # type: ignore[no-any-return]

    def get_ssl_context(self, module: ModuleType) -> Union[SSLContext, None]:
        if self.ssl_context_factory_name is None:
            return None
        else:
            try:
                attr = getattr(module, self.ssl_context_factory_name)
            except AttributeError:
                raise AdevConfigError("Module '{}' does not define a '{}' attribute/class".format(
                    self.py_file.name, self.ssl_context_factory_name))
        ssl_context = attr()
        if isinstance(ssl_context, SSLContext):
            return ssl_context
        else:
            raise AdevConfigError("ssl-context-factory '{}' in module '{}' didn't return valid SSLContext".format(
                self.ssl_context_factory_name, self.py_file.name))

    async def load_app(self, app_factory: AppFactory) -> web.Application:
        if isinstance(app_factory, web.Application):
            return app_factory

        app = app_factory()

        if asyncio.iscoroutine(app):
            app = await app

        if not isinstance(app, web.Application):
            raise AdevConfigError("app factory '{}' returned '{}' not an aiohttp.web.Application".format(
                self.app_factory_name, app.__class__.__name__))

        return app

    def __str__(self) -> str:
        fields = ("py_file", "static_path", "static_url", "livereload", "shutdown_by_url",
                  "path_prefix", "app_factory_name", "host", "bind_address", "main_port", "aux_port")
        return 'Config:\n' + '\n'.join('  {0}: {1!r}'.format(f, getattr(self, f)) for f in fields)
