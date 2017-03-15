import base64
import os
import re
from enum import Enum
from pathlib import Path

from isort import SortImports
from jinja2 import Template, TemplateError

from ..exceptions import AiohttpDevConfigError
from ..logs import main_logger as logger

THIS_DIR = Path(__file__).parent
TEMPLATE_DIR = THIS_DIR / 'template'  # type: Path

FILES_REGEXES = {
    '.py': [
        ('^ *# *\n', '', re.M),    # blank comments
        ('\n *# *$', '', 0),       # blank comment at end of fie
        ('\n{4,}', '\n\n\n', 0),   # more than 2 empty lines
        ('^\s+', '', 0),           # leading new lines
    ],
    '.sh': [
        ('^ *# *\n', '', re.M),    # blank comments
        ('\n *# *$', '', 0),       # blank comment at end of fie
    ],
}

FILES_REGEXES = {k: [(re.compile(p, f), r) for p, r, f in v] for k, v in FILES_REGEXES.items()}


class TemplateChoice(str, Enum):
    """
    Template Engine

    Please choose which template engine you wish to use.
    * with "jinja" views will be rendered using Jinja2 templates using aiohttp-jinja2.
    * with "none" views will be rendered directly.
    """
    JINJA = 'jinja'  # default
    NONE = 'none'


class SessionChoices(str, Enum):
    """
    Session

    Please choose how you want sessions to be managed.
    * "secure" will implemented encrypted cookie sessions using aiohttp-session
    * "none" will mean no sessions
    """
    SECURE = 'secure'  # default
    # * "redis" will use redis to store session data
    # REDIS = 'redis' TODO
    NONE = 'none'


class DatabaseChoice(str, Enum):
    """
    Database

    Please choose which database backend you wish to use.
    * "pg-sqlalchemy" will use postgresql via aiopg and the SqlAlchemy ORM
    * "none" will use no database, persistence in examples is achieved by simply writing to file
    """
    PG_SA = 'pg-sqlalchemy'  # default
    # * "pg-raw" will use postgresql via aiopg with no ORM
    # PG_RAW = 'pg-raw' TODO
    NONE = 'none'


class ExampleChoice(str, Enum):
    """
    Example

    Please choose whether you want a simple example "message board" app to be created demonstrating a little
    more of aiohttp's usage than the single simple view created with "none".
    """
    MESSAGE_BOARD = 'message-board'  # default
    NONE = 'none'


def enum_choices(enum):
    return [m.value for m in enum.__members__.values()]


def enum_default(enum):
    return next(v for v in enum.__members__.values())


def check_dir_clean(d: Path):
    if d.exists():
        existing_paths = {p.name for p in d.iterdir()}
        new_paths = {p.name for p in TEMPLATE_DIR.iterdir()}
        conflicts = existing_paths & new_paths
        if conflicts:
            raise AiohttpDevConfigError('The path "{}" already has files/directories which would conflict '
                                        'with the new project: {}'.format(d, ', '.join(sorted(conflicts))))


class StartProject:
    def __init__(self, *,
                 path: str,
                 name: str,
                 template_engine: TemplateChoice=enum_default(TemplateChoice),
                 session: SessionChoices=enum_default(SessionChoices),
                 database: DatabaseChoice=enum_default(DatabaseChoice),
                 example: ExampleChoice=enum_default(ExampleChoice),
                 template_dir: Path=TEMPLATE_DIR) -> None:
        self.project_root = Path(path)
        self.template_dir = template_dir
        check_dir_clean(self.project_root)

        try:
            display_path = self.project_root.relative_to(Path('.').resolve())
        except ValueError:
            display_path = self.project_root

        logger.info('Starting new aiohttp project "%s" at "%s"', name, display_path)
        display_config = [
            ('template_engine', template_engine),
            ('session', session),
            ('database', database),
            ('example', example),
        ]
        logger.info('config:\n%s', '\n'.join('    {}: {}'.format(*c) for c in display_config))
        self.ctx = {
            'name': name,
            'clean_name': re.sub('[^\w_]', '', re.sub('[.-]', '_', name)),
            'cookie_secret_key': base64.urlsafe_b64encode(os.urandom(32)).decode(),
            'template_engine': self._choice_context(template_engine, TemplateChoice),
            'session': self._choice_context(session, SessionChoices),
            'database': self._choice_context(database, DatabaseChoice),
            'example': self._choice_context(example, ExampleChoice),
        }
        self.files_created = 0
        self.generate_directory(TEMPLATE_DIR)
        logger.info('project created, %d files generated', self.files_created)

    def _choice_context(self, value, enum):
        return {'is_' + o.replace('-', '_'): value == o for o in enum_choices(enum)}

    def generate_directory(self, p: Path):
        for pp in p.iterdir():
            if pp.is_dir():
                self.generate_directory(pp)
            else:
                assert pp.is_file()
                if not pp.name.endswith('.pyc'):
                    self.generate_file(pp)

    def generate_file(self, p: Path):
        try:
            template = Template(p.read_text())
            text = template.render(**self.ctx)
        except TemplateError as e:
            raise TemplateError('error in {}'.format(p)) from e
        text = text.strip('\n\t ')
        new_path = self.project_root / p.relative_to(self.template_dir)
        if len(text) < 3:
            # empty files don't get created, in case a few characters get left behind
            logger.debug('not creating "%s", as it would be empty', new_path)
            return
        logger.debug('creating "%s"', new_path)

        if p.name == 'requirements.txt':
            packages = {p.strip() for p in text.split('\n') if p.strip() and p.strip() != '#'}
            text = '\n'.join(sorted(packages))
        else:
            # helpful when debugging: print(text.replace(' ', '·').replace('\n', '⏎\n'))
            if p.suffix == '.py':
                text = SortImports(file_contents=text).output

            regexes = FILES_REGEXES.get(p.suffix, [])
            for regex, repl in regexes:
                text = regex.sub(repl, text)

        # re-add a trailing newline accounting for newlines added by PY_REGEXES
        text = re.sub('\n*$', '\n', text)
        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_text(text)
        self.files_created += 1
