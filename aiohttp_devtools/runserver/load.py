import os
import re
import sys
from importlib import import_module
from pathlib import Path
from typing import Dict

import trafaret as t
from trafaret_config import ConfigError, read_and_validate

from ..exceptions import AiohttpDevConfigError as AdConfigError
from ..logs import rs_dft_logger as logger


STD_FILE_NAMES = [
    re.compile('settings\.ya?ml'),
    re.compile('main\.py'),
    re.compile('app\.py'),
]


def find_app_path(app_path: str) -> Path:
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
    raise AdConfigError('unable to find a recognised default file ("settings.yml", "app.py" or "main.py") '
                        'in the directory "%s"' % app_path)


DEV_DICT = t.Dict({
    'app_path': t.String,
    t.Key('static_path', default=None): t.Or(t.String | t.Null),
    t.Key('static_url', default='/static/'): t.String,
    t.Key('livereload', default=True): t.Bool,
    t.Key('debug_toolbar', default=True): t.Bool,
    t.Key('app_factory', default=None): t.Or(t.String | t.Null),
    t.Key('main_port', default=8000): t.Int(gte=0),
    t.Key('aux_port', default=8001): t.Int(gte=0),
})

SETTINGS = t.Dict({'dev': DEV_DICT})
SETTINGS.allow_extra('*')


def load_settings_file(settings_path: Path, **kwargs) -> Dict:
    """
    Load a settings file (or simple python file) and return settings after overwriting with any non null kwargs
    :param path: path to load file from
    :param kwargs: kwargs from cli or runserver direct all
    :return: config dict compliant with DEV_DICT above
    """
    active_kwargs = {k: v for k, v in kwargs.items() if v is not None}
    try:
        if re.search('\.ya?ml$', settings_path.name):
            logger.debug('setting file found, loading yaml and overwriting with kwargs')
            try:
                _data = read_and_validate(str(settings_path), SETTINGS)
            except ConfigError as e:
                raise AdConfigError('Invalid settings file, {}'.format(e)) from e

            _kwargs = {'app_path': '.'}  # to avoid trafaret failing
            _kwargs.update(active_kwargs)
            validated_kwargs = DEV_DICT.check(_kwargs)

            config = _data['dev']

            # we only overwrite config with validated_kwargs where the original key existed to avoid overwriting
            # settings values with defaults from DEV_DICT
            for k in active_kwargs.keys():
                config[k] = validated_kwargs[k]

            config['settings_file'] = settings_path
            config['static_path'] = _resolve_path(config, 'static_path', is_file=False)
            config['app_path'] = _resolve_path(config, 'app_path', is_file=True)
            return config
        elif re.search('\.py$', settings_path.name):
            logger.debug('python file found, using it directly together with kwargs config')
            active_kwargs['app_path'] = str(settings_path)
            return DEV_DICT.check(active_kwargs)
    except t.DataError as e:
        raise AdConfigError('Invalid key word arguments {}'.format(e)) from e

    raise AdConfigError('Unknown extension for app_path: %s, should be .py or .yml' % settings_path.name)


def _resolve_path(config: Dict, attr: str, is_file):
    path = config[attr]
    if path is None:
        return
    try:
        path = config['settings_file'].parent.joinpath(path).resolve()
        if is_file:
            assert path.is_file()
        else:
            assert path.is_dir()
    except (OSError, AssertionError) as e:
        raise ConfigError('{attr} "{{attr}}" is not a valid '
                          'directory relative to {settings_file}'.format(attr=attr, **config)) from e
    return path


APP_FACTORY_NAMES = [
    'app',
    'app_factory',
    'get_app',
    'create_app',
]


def import_string(file_path, attr_name=None, _trying_again=False):
    """
    Import attribute/class from from a python module. Raise ImportError if the import failed.

    Approximately stolen from django.

    :param file_path: path to python module
    :param attr_name: attribute to get from module
    :return: (attribute, Path object for directory of file)
    """
    try:
        file_path = Path(file_path).resolve().relative_to(Path('.').resolve())
    except ValueError as e:
        raise AdConfigError('unable to import "%s" path is not relative '
                            'to the current working directory' % file_path) from e

    module_path = str(file_path).replace('.py', '').replace('/', '.')

    try:
        module = import_module(module_path)
    except ImportError as e:
        if _trying_again:
            raise AdConfigError('error importing {}'.format(module_path)) from e
        logger.debug('ImportError while loading %s, adding CWD to pythonpath and try again', module_path)
        p = os.getcwd()
        logger.debug('adding current working director %s to pythonpath and reattempting import', p)
        sys.path.append(p)
        return import_string(file_path, attr_name, True)
    return find_attr(attr_name, module, module_path)


def find_attr(attr_name, module, module_path):
    if attr_name is None:
        try:
            attr_name = next(an for an in APP_FACTORY_NAMES if hasattr(module, an))
        except StopIteration as e:
            raise AdConfigError('No name supplied and no default app factory found in "%s"' % module_path) from e
        else:
            logger.debug('found default attribute "%s" in module "%s"' % (attr_name, module))

    try:
        attr = getattr(module, attr_name)
    except AttributeError as e:
        raise AdConfigError('Module "%s" does not define a "%s" attribute/class' % (module_path, attr_name)) from e

    directory = Path(module.__file__).parent
    return attr, directory
