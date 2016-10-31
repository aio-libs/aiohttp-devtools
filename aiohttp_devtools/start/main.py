import re
from pathlib import Path

from isort import SortImports
from jinja2 import Template, TemplateError

from ..exceptions import ConfigError
from ..logs import start_logger as logger

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


class Options:
    # could use Enums here but they wouldn't play well with click
    NONE = 'none'

    TEMPLATE_ENG_JINJA2 = 'jinja2'
    TEMPLATE_ENG_CHOICES = (TEMPLATE_ENG_JINJA2, NONE)

    SESSION_SECURE = 'secure'
    SESSION_VANILLA = 'vanilla'
    SESSION_REDIS = 'redis'
    SESSION_CHOICES = (SESSION_SECURE, SESSION_VANILLA, SESSION_REDIS, NONE)

    DB_PG_SA = 'postgres-sqlalchemy'
    DB_PG_RAW = 'postgres-raw'
    DB_CHOICES = (DB_PG_SA, DB_PG_RAW, NONE)

    EXAMPLE_MESSAGE_BOARD = 'message-board'
    EXAMPLE_CHOICES = (EXAMPLE_MESSAGE_BOARD, NONE)


class StartProject:
    def __init__(self, *,
                 path: str,
                 name: str,
                 template_engine: str=Options.TEMPLATE_ENG_JINJA2,
                 session: str=Options.SESSION_SECURE,
                 database: str=Options.DB_PG_SA,
                 example: str=Options.EXAMPLE_MESSAGE_BOARD,
                 template_dir: Path=TEMPLATE_DIR) -> None:
        self.project_root = Path(path)
        self.template_dir = template_dir
        if self.project_root.exists():
            existing_paths = {p.name for p in self.project_root.iterdir()}
            new_paths = {p.name for p in TEMPLATE_DIR.iterdir()}
            conflicts = existing_paths & new_paths
            if conflicts:
                raise ConfigError("The path you supplied already has files/directories which would conflict "
                                  "with the new project: {}".format(', '.join(sorted(conflicts))))

        display_path = self.project_root.relative_to(Path('.').resolve())
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
            'template_engine': self._choice_context(template_engine, Options.TEMPLATE_ENG_CHOICES),
            'session': self._choice_context(session, Options.SESSION_CHOICES),
            'database': self._choice_context(database, Options.DB_CHOICES),
            'example': self._choice_context(example, Options.EXAMPLE_CHOICES),
        }
        self.files_created = 0
        self.generate_directory(TEMPLATE_DIR)
        logger.info('project created, %d files generated', self.files_created)

    def _choice_context(self, value, choices):
        return {'is_' + o.replace('-', '_'): value == o for o in choices}

    def generate_directory(self, p: Path):
        for pp in p.iterdir():
            if pp.is_dir():
                self.generate_directory(pp)
            elif pp.is_file():
                self.generate_file(pp)

    def generate_file(self, p: Path):
        try:
            template = Template(p.read_text())
            text = template.render(**self.ctx)
        except TemplateError as e:
            raise TemplateError('error in {}'.format(p)) from e
        text = text.strip('\n\t ')
        new_path = self.project_root / p.relative_to(self.template_dir)
        if not text and p.name != '__init__.py':
            # empty files don't get created
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
