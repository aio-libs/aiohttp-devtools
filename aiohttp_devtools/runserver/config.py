import asyncio
import inspect
import re
import sys
from importlib import import_module
from pathlib import Path

from aiohttp import web

from ..exceptions import AiohttpDevConfigError as AdevConfigError
from ..logs import rs_dft_logger as logger

STD_FILE_NAMES = [
    re.compile('main\.py'),
    re.compile('app\.py'),
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
                 app_path: str='.',
                 root_path: str=None,
                 verbose: bool=False,
                 static_path: str=None,
                 python_path: str=None,
                 static_url: str='/static/',
                 livereload: bool=True,
                 debug_toolbar: bool=False,  # TODO set True once debug toolbar is fixed
                 app_factory_name: str=None,
                 host: str=INFER_HOST,
                 main_port: int=8000,
                 aux_port: int=None):
        if root_path:
            self.root_path = Path(root_path).resolve()
            logger.debug('Root path specified: %s', self.root_path)
        else:
            logger.debug('Root path not specified, using current working directory')
            self.root_path = Path('.').resolve()

        self.app_path = self._find_app_path(app_path)
        if not self.app_path.name.endswith('.py'):
            raise AdevConfigError('Unexpected extension for app_path: %s, should be .py' % self.app_path.name)
        self.verbose = verbose
        self.settings_found = False

        self.py_file = self._resolve_path(str(self.app_path), 'is_file', 'app-path')
        self.python_path = self._resolve_path(python_path, 'is_dir', 'python-path') or self.root_path

        self.static_path = self._resolve_path(static_path, 'is_dir', 'static-path')
        self.static_url = static_url
        self.livereload = livereload
        self.debug_toolbar = debug_toolbar
        self.app_factory_name = app_factory_name
        self.infer_host = host == INFER_HOST
        self.host = 'localhost' if self.infer_host else host
        self.main_port = main_port
        self.aux_port = aux_port or (main_port + 1)
        self.code_directory = None
        logger.debug('config loaded:\n%s', self)

    @property
    def static_path_str(self):
        return self.static_path and str(self.static_path)

    def _find_app_path(self, app_path: str) -> Path:
        path = (self.root_path / app_path).resolve()
        if path.is_file():
            logger.debug('app_path is a file, returning it directly')
            return path

        assert path.is_dir()
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

    def _resolve_path(self, _path: str, check: str, arg_name: str):
        if _path is None:
            return

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

    def import_app_factory(self):
        """
        Import attribute/class from from a python module. Raise AdevConfigError if the import failed.

        :return: (attribute, Path object for directory of file)
        """
        rel_py_file = self.py_file.relative_to(self.python_path)
        module_path = '.'.join(rel_py_file.with_suffix('').parts)

        sys.path.append(str(self.python_path))
        try:
            module = import_module(module_path)
        except ImportError as e:
            raise AdevConfigError('error importing "{}" '
                                  'from "{}": {}'.format(module_path, self.python_path, e)) from e

        logger.debug('successfully loaded "%s" from "%s"', module_path, self.python_path)

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
        except AttributeError as e:
            raise AdevConfigError('Module "{s.py_file.name}" '
                                  'does not define a "{s.app_factory_name}" attribute/class'.format(s=self)) from e

        self.code_directory = Path(module.__file__).parent
        return attr

    async def load_app(self):
        app_factory = self.import_app_factory()
        if isinstance(app_factory, web.Application):
            app = app_factory
        else:
            # app_factory should be a proper factory with signature (loop): -> Application
            signature = inspect.signature(app_factory)
            if 'loop' in signature.parameters:
                loop = asyncio.get_event_loop()
                app = app_factory(loop=loop)
            else:
                # loop argument missing, assume no arguments
                app = app_factory()

            if asyncio.iscoroutine(app):
                app = await app

            if not isinstance(app, web.Application):
                raise AdevConfigError('app factory "{.app_factory_name}" returned "{.__class__.__name__}" not an '
                                      'aiohttp.web.Application'.format(self, app))

        return app

    def __str__(self):
        fields = ('py_file', 'static_path', 'static_url', 'livereload', 'debug_toolbar',
                  'app_factory_name', 'host', 'main_port', 'aux_port')
        return 'Config:\n' + '\n'.join('  {0}: {1!r}'.format(f, getattr(self, f)) for f in fields)
