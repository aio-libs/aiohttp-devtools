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
    '.yml': [
        ('^ *# *\n', '', re.M),    # blank comments
        ('\n *# *$', '', 0),       # blank comment at end of fie
    ],
}

FILES_REGEXES = {k: [(re.compile(p, f), r) for p, r, f in v] for k, v in FILES_REGEXES.items()}


class TemplateChoice(str, Enum):
    """
    Template Engines

    Please choose which template engine you wish to use. With "none" views will be rendered directly.
    """
    JINJA = 'jinja'
    NONE = 'none'

    @classmethod
    def default(cls):
        return cls.JINJA


class SessionChoices(str, Enum):
    """
    Sessions

    Please choose how you want sessions to be managed.
    * "none" will mean no sessions
    * "secure" will use encrypted cookies
    * "redis" will use redis to store session data
    """
    SECURE = 'secure'
    REDIS = 'redis'
    NONE = 'none'

    @classmethod
    def default(cls):
        return cls.SECURE


class DatabaseChoice(str, Enum):
    """
    Databases

    Please choose which database backend you wish to use.
    """
    PG_SA = 'pg-sqlalchemy'
    PG_RAW = 'pg-raw'
    NONE = 'none'

    @classmethod
    def default(cls):
        return cls.PG_SA


class ExampleChoice(str, Enum):
    """
    Example

    Please choose whether you want a simple example "message board" app to be created.
    """
    MESSAGE_BOARD = 'message-board'
    NONE = 'none'

    @classmethod
    def default(cls):
        return cls.MESSAGE_BOARD


class StartProject:
    def __init__(self, *,
                 path: str,
                 name: str,
                 template_engine: TemplateChoice=TemplateChoice.default(),
                 session: SessionChoices=SessionChoices.default(),
                 database: DatabaseChoice=DatabaseChoice.default(),
                 example: ExampleChoice=ExampleChoice.default(),
                 template_dir: Path=TEMPLATE_DIR) -> None:
        self.project_root = Path(path)
        self.template_dir = template_dir
        if self.project_root.exists():
            existing_paths = {p.name for p in self.project_root.iterdir()}
            new_paths = {p.name for p in TEMPLATE_DIR.iterdir()}
            conflicts = existing_paths & new_paths
            if conflicts:
                raise AiohttpDevConfigError('The path you supplied already has files/directories which would conflict '
                                            'with the new project: {}'.format(', '.join(sorted(conflicts))))

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
            'template_engine': self._choice_context(template_engine, TemplateChoice),
            'session': self._choice_context(session, SessionChoices),
            'database': self._choice_context(database, DatabaseChoice),
            'example': self._choice_context(example, ExampleChoice),
        }
        self.files_created = 0
        self.generate_directory(TEMPLATE_DIR)
        logger.info('project created, %d files generated', self.files_created)

    def _choice_context(self, value, choice_enum):
        return {'is_' + o.replace('-', '_'): value == o for o in choice_enum.__members__.values()}

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
            packages = {p.strip() for p in text.split('\n') if p.strip()}
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
