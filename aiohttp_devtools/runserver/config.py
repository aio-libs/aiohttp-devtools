import re
import sys
from importlib import import_module
from pathlib import Path
from typing import Dict

import trafaret as t
from aiohttp.web import Application
from trafaret_config import ConfigError, read_and_validate

from ..exceptions import AiohttpDevConfigError as AdevConfigError
from ..logs import rs_dft_logger as logger

STD_FILE_NAMES = [
    re.compile('settings\.ya?ml'),
    re.compile('main\.py'),
    re.compile('app\.py'),
]


DEV_DICT = t.Dict({
    'py_file': t.String,
    t.Key('static_path', default=None): t.Or(t.String | t.Null),
    t.Key('python_path', default=None): t.Or(t.String | t.Null),
    t.Key('static_url', default='/static/'): t.String,
    t.Key('livereload', default=True): t.Bool,
    t.Key('debug_toolbar', default=True): t.Bool,
    t.Key('pre_check', default=True): t.Bool,
    t.Key('app_factory', default=None) >> 'app_factory_name': t.Or(t.String | t.Null),
    t.Key('main_port', default=8000): t.Int(gte=0),
    t.Key('aux_port', default=8001): t.Int(gte=0),
})

SETTINGS = t.Dict({'dev': DEV_DICT})
SETTINGS.allow_extra('*')


APP_FACTORY_NAMES = [
    'app',
    'app_factory',
    'get_app',
    'create_app',
]


class Config:
    def __init__(self, app_path: str, verbose=False, **kwargs):
        self.app_path = self._find_app_path(app_path)
        self.verbose = verbose
        self.settings_found = False
        config = self._load_settings_file(**kwargs)

        if self.settings_found:
            logger.debug('Loaded settings file, using it directory as root')
            self.root_dir = self.app_path.parent.resolve()
        else:
            logger.debug('Loaded python file, using working directory as root')
            self.root_dir = Path('.').resolve()

        self.py_file = self._resolve_path(config, 'py_file', 'is_file')
        self.python_path = self._resolve_path(config, 'python_path', 'is_dir') or self.root_dir

        self.static_path = self._resolve_path(config, 'static_path', 'is_dir')
        self.static_url = config['static_url']
        self.livereload = config['livereload']
        self.debug_toolbar = config['debug_toolbar']
        self.pre_check = config['pre_check']
        self.app_factory_name = config['app_factory_name']
        self.main_port = config['main_port']
        self.aux_port = config['aux_port']
        self.app_factory, self.code_directory = self._import_app_factory()

    @property
    def static_path_str(self):
        return self.static_path and str(self.static_path)

    @property
    def code_directory_str(self):
        return self.code_directory and str(self.code_directory)

    def _find_app_path(self, app_path: str) -> Path:
        path = Path(app_path).resolve()
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
        raise AdevConfigError('unable to find a recognised default file ("settings.yml", "app.py" or "main.py") '
                              'in the directory "%s"' % app_path)

    def _load_settings_file(self, **kwargs) -> Dict:
        """
        Load a settings file (or simple python file) and return settings after overwriting with any non null kwargs
        :param path: path to load file from
        :param kwargs: kwargs from cli or runserver direct all
        :return: config dict compliant with DEV_DICT above
        """
        active_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        try:
            if re.search('\.ya?ml$', self.app_path.name):
                logger.debug('setting file found, loading yaml and overwriting with kwargs')
                self.settings_found = True
                try:
                    _data = read_and_validate(str(self.app_path), SETTINGS)
                except ConfigError as e:
                    raise AdevConfigError('Invalid settings file, {}'.format(e)) from e

                _kwargs = {'py_file': 'void.py'}  # to avoid trafaret failing
                _kwargs.update(active_kwargs)
                validated_kwargs = DEV_DICT.check(_kwargs)

                config = _data['dev']

                # we only overwrite config with validated_kwargs where the original key existed to avoid overwriting
                # settings values with defaults from DEV_DICT
                for k in active_kwargs.keys():
                    config[k] = validated_kwargs[k]

                return config
            elif re.search('\.py$', self.app_path.name):
                logger.debug('python file found, using it directly together with kwargs config')
                active_kwargs['py_file'] = str(self.app_path)
                return DEV_DICT.check(active_kwargs)
        except t.DataError as e:
            raise AdevConfigError('Invalid key word arguments {}'.format(e)) from e

        raise AdevConfigError('Unknown extension for app_path: %s, should be .py or .yml' % self.app_path.name)

    def _resolve_path(self, config: Dict, attr: str, check: str):
        _path = config[attr]
        if _path is None:
            return

        if _path.startswith('/'):
            path = Path(_path)
            error_msg = '{attr} "{path}" is not a valid path'
        else:
            path = Path(self.root_dir / _path)
            error_msg = '{attr} "{path}" is not a valid path relative to {root}'

        try:
            path = path.resolve()
        except OSError as e:
            raise AdevConfigError(error_msg.format(attr=attr, path=_path, root=self.root_dir)) from e

        if check == 'is_file':
            if not path.is_file():
                raise AdevConfigError('{} is not a file'.format(path))
        else:
            assert check == 'is_dir'
            if not path.is_dir():
                raise AdevConfigError('{} is not a directory'.format(path))
        return path

    def _import_app_factory(self):
        """
        Import attribute/class from from a python module. Raise AdevConfigError if the import failed.

        :return: (attribute, Path object for directory of file)
        """

        sys.path.append(str(self.python_path))

        rel_py_file = self.py_file.relative_to(self.python_path)
        module_path = str(rel_py_file).replace('.py', '').replace('/', '.')

        try:
            module = import_module(module_path)
        except ImportError as e:
            raise AdevConfigError('error importing "{}" from "{}": {}'.format(module_path, self.python_path, e)) from e

        logger.debug('successfully loaded "%s" from "%s"', module_path, self.python_path)

        if self.app_factory_name is None:
            try:
                self.app_factory_name = next(an for an in APP_FACTORY_NAMES if hasattr(module, an))
            except StopIteration as e:
                raise AdevConfigError('No name supplied and no default app factory '
                                      'found in {s.py_file.name}'.format(s=self)) from e
            else:
                logger.debug('found default attribute "%s" in module "%s"', self.app_factory_name, module)

        try:
            attr = getattr(module, self.app_factory_name)
        except AttributeError as e:
            raise AdevConfigError('Module "{s.py_file.name}" '
                                  'does not define a "{s.app_factory_name}" attribute/class'.format(s=self)) from e

        directory = Path(module.__file__).parent
        return attr, directory

    def check(self, loop):
        """
        run the app factory as a very basic check it's working and returns the right thing,
        this should catch config errors and database connection errors.
        """
        if not self.pre_check:
            logger.debug('pre-check disabled, not checking app factory')
            return
        logger.info('pre-check enabled, checking app factory')
        if not callable(self.app_factory):
            raise AdevConfigError('app_factory "{.app_factory_name}" is not callable'.format(self))
        try:
            app = self.app_factory(loop)
        except ConfigError as e:
            raise AdevConfigError('app factory "{.app_factory_name}" caused ConfigError: {}'.format(self, e)) from e
        if not isinstance(app, Application):
            raise AdevConfigError('app factory "{.app_factory_name}" returned "{.__class__.__name__}" not an '
                                  'aiohttp.web.Application'.format(self, app))
        logger.debug('app "%s" successfully created', app)
        loop.run_until_complete(self._startup_cleanup(app))

    async def _startup_cleanup(self, app):
        logger.debug('running app startup...')
        await app.startup()
        logger.debug('running app cleanup...')
        await app.cleanup()

    def __str__(self):
        fields = ('py_file', 'static_path', 'static_url', 'livereload', 'debug_toolbar', 'pre_check',
                  'app_factory_name', 'main_port', 'aux_port',)
        return 'Config:\n' + '\n'.join('  {0}: {1!r}'.format(f, getattr(self, f)) for f in fields)
