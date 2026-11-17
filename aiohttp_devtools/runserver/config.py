import asyncio
import re
import sys
from collections.abc import Awaitable, Callable
from importlib import import_module
from pathlib import Path
from typing import Literal
from types import ModuleType

from aiohttp import web
from ssl import SSLContext, SSLError, create_default_context as create_default_ssl_context

import __main__
from ..exceptions import AiohttpDevConfigError as AdevConfigError
from ..logs import rs_dft_logger as logger

AppFactory = web.Application | Callable[[], web.Application] | Callable[[], Awaitable[web.Application]]

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

INFER_HOST = '<inference>'


class Config:
    def __init__(self, *,
                 app_path: str = '.',
                 root_path: str | None = None,
                 verbose: bool = False,
                 static_path: str | None = None,
                 python_path: str | None = None,
                 static_url: str = '/static/',
                 livereload: bool = True,
                 shutdown_by_url: bool = sys.platform.startswith("win32"),
                 path_prefix: str = "/_devtools",
                 app_factory_name: str | None = None,
                 host: str = INFER_HOST,
                 bind_address: str = "localhost",
                 main_port: int = 8000,
                 aux_port: int | None = None,
                 browser_cache: bool = False,
                 ssl_context_factory_name: str | None = None,
                 ssl_rootcert_file_path: str | None = None):
        if root_path:
            self.root_path = Path(root_path).resolve()
            logger.debug('Root path specified: %s', self.root_path)
            self.watch_path: Path | None = self.root_path
        else:
            logger.debug('Root path not specified, using current working directory')
            self.root_path = Path('.').resolve()
            self.watch_path = None

        self.app_path = self._find_app_path(app_path)
        if not self.app_path.name.endswith('.py'):
            raise AdevConfigError(f'Unexpected extension for app_path: {self.app_path.name}, should be .py')
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
        self.main_port = main_port
        self.aux_port = aux_port or (main_port + 1)
        self.browser_cache = browser_cache
        self.ssl_context_factory_name = ssl_context_factory_name
        self.ssl_rootcert_file_path = ssl_rootcert_file_path
        logger.debug('config loaded:\n%s', self)

    @property
    def protocol(self) -> Literal["http", "https"]:
        return "http" if self.ssl_context_factory_name is None else "https"

    @property
    def static_path_str(self) -> str | None:
        return str(self.static_path) if self.static_path else None

    @property
    def client_ssl_context(self) -> SSLContext | bool:
        client_ssl_context: SSLContext | bool = True
        if self.protocol == "https":
            client_ssl_context = create_default_ssl_context()
            if self.ssl_rootcert_file_path:
                try:
                    client_ssl_context.load_verify_locations(self.ssl_rootcert_file_path)
                except FileNotFoundError:
                    raise AdevConfigError(f"No such file or directory: {self.ssl_rootcert_file_path}")
                except SSLError:
                    raise AdevConfigError(f"invalid root cert file: {self.ssl_rootcert_file_path}")
        return client_ssl_context

    def _find_app_path(self, app_path: str) -> Path:
        # for backwards compatibility try this first
        path = (self.root_path / app_path).resolve()
        if not path.exists():
            path = Path(app_path).resolve()
        if path.is_file():
            logger.debug('app_path is a file, returning it directly')
            return path

        assert path.is_dir(), f'app_path {path} is not a directory'
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
                              f'in the directory "{app_path}"')

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
                raise AdevConfigError(f'{path} is not a file')
        else:
            assert check == 'is_dir'
            if not path.is_dir():
                raise AdevConfigError(f'{path} is not a directory')
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
                                      f'found in {self.py_file.name}') from e
            else:
                logger.debug('found default attribute "%s" in module "%s"',
                             self.app_factory_name, module)

        try:
            attr = getattr(module, self.app_factory_name)
        except AttributeError:
            raise AdevConfigError(
                f"Module '{self.py_file.name}' does not define a '{self.app_factory_name}' attribute/class")

        if not isinstance(attr, web.Application) and not callable(attr):
            raise AdevConfigError(f"'{self.py_file.name}.{self.app_factory_name}' is not an Application or callable")

        if hasattr(attr, "__code__"):
            required_args = attr.__code__.co_argcount - len(attr.__defaults__ or ())
            if required_args > 0:
                raise AdevConfigError(
                    f"'{self.py_file.name}.{self.app_factory_name}' should not have required arguments.")

        return attr  # type: ignore[no-any-return]

    def get_ssl_context(self, module: ModuleType) -> SSLContext | None:
        if self.ssl_context_factory_name is None:
            return None
        else:
            try:
                attr = getattr(module, self.ssl_context_factory_name)
            except AttributeError:
                raise AdevConfigError(f"Module '{self.py_file.name}' does not define "
                                      f"a '{self.ssl_context_factory_name}' attribute/class")
        ssl_context = attr()
        if isinstance(ssl_context, SSLContext):
            return ssl_context
        else:
            raise AdevConfigError(f"ssl-context-factory '{self.ssl_context_factory_name}' in module "
                                  f"'{self.py_file.name}' didn't return valid SSLContext")

    async def load_app(self, app_factory: AppFactory) -> web.Application:
        if isinstance(app_factory, web.Application):
            return app_factory

        app = app_factory()

        if asyncio.iscoroutine(app):
            app = await app

        if not isinstance(app, web.Application):
            raise AdevConfigError(f"app factory '{self.app_factory_name}' returned "
                                  f"'{app.__class__.__name__}' not an aiohttp.web.Application")

        return app

    def __str__(self) -> str:
        fields = ("py_file", "static_path", "static_url", "livereload", "shutdown_by_url",
                  "path_prefix", "app_factory_name", "host", "bind_address", "main_port", "aux_port")
        return 'Config:\n' + '\n'.join(f'  {f}: {getattr(self, f)!r}' for f in fields)
