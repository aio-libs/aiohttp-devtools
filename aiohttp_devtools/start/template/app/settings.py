import os
from pathlib import Path


class Required:
    def __init__(self, v_type=None):
        self.v_type = v_type


class Settings:
    """
    Any setting defined here can be overridden by:

    Settings the appropriate environment variable, eg. to override FOOBAR, `export APP_FOOBAR="whatever"`.
    This is useful in production for secrets you do not wish to save in code and
    also plays nicely with docker(-compose). Settings will attempt to convert environment variables to match the
    type of the value here. See also activate.settings.sh.

    Or, passing the custom setting as a keyword argument when initialising settings (useful when testing)
    """
    _ENV_PREFIX = 'APP_'
    # {% if database.is_none and example.is_message_board %}
    MESSAGE_FILE = Path('./messages.txt')
    # {% elif database.is_pg_sqlalchemy %}
    DB_NAME = '{{ clean_name }}'
    DB_USER = 'postgres'
    DB_PASSWORD = Required(str)
    DB_HOST = 'localhost'
    DB_PORT = '5432'
    # {% endif %}
    # {% if session.is_secure %}
    # you should replace this with another value via the environment variable APP_COOKIE_SECRET
    # which is not saved in code, you could also use Required(str) to force the env variable to be set.
    COOKIE_SECRET = '{{ cookie_secret_key }}'
    # {% endif %}

    def __init__(self, **custom_settings):
        """
        :param custom_settings: Custom settings to override defaults, only attributes already defined can be set.
        """
        self._custom_settings = custom_settings
        self.substitute_environ()
        for name, value in custom_settings.items():
            if not hasattr(self, name):
                raise TypeError('{} is not a valid setting name'.format(name))
            setattr(self, name, value)

    def substitute_environ(self):
        """
        Substitute environment variables into settings.
        """
        for attr_name in dir(self):
            if attr_name.startswith('_') or attr_name.upper() != attr_name:
                continue

            orig_value = getattr(self, attr_name)
            is_required = isinstance(orig_value, Required)
            orig_type = orig_value.v_type if is_required else type(orig_value)
            env_var_name = self._ENV_PREFIX + attr_name
            env_var = os.getenv(env_var_name, None)
            if env_var is not None:
                if issubclass(orig_type, bool):
                    env_var = env_var.upper() in ('1', 'TRUE')
                elif issubclass(orig_type, int):
                    env_var = int(env_var)
                elif issubclass(orig_type, Path):
                    env_var = Path(env_var)
                elif issubclass(orig_type, bytes):
                    env_var = env_var.encode()
                # could do floats here and lists etc via json
                setattr(self, attr_name, env_var)
            elif is_required and attr_name not in self._custom_settings:
                raise RuntimeError('The required environment variable "{0}" is currently not set, '
                                   'you\'ll need to run `source activate.settings.sh` '
                                   'or you can set that single environment variable with '
                                   '`export {0}="<value>"`'.format(env_var_name))
