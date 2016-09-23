import re
from pathlib import Path

from aiohttp_devtools.exceptions import ConfigError
from jinja2 import Template, TemplateError

THIS_DIR = Path(__file__).parent
TEMPLATE_DIR = THIS_DIR / 'template'  # type: Path

PY_REGEXES = [(re.compile(p, f), r) for p, r, f in [
    ('^ *# *\n', '', re.M),    # blank comments
    ('\n *# *$', '', 0),       # blank comment at end of fie
    ('\n{4,}', '\n\n\n', 0)  # more than 2 empty lines
]]


class Options:
    # could use Enums here but they wouldn't play well with click
    NONE = 'none'

    TEMPLATE_ENG_JINJA2 = 'jinja2'
    TEMPLATE_ENG_CHOICES = (NONE, TEMPLATE_ENG_JINJA2)

    SESSION_SECURE = 'secure'
    SESSION_VANILLA = 'vanilla'
    SESSION_REDIS = 'redis'
    SESSION_CHOICES = (NONE, SESSION_SECURE, SESSION_VANILLA, SESSION_REDIS)

    DB_PG_SA = 'postgres-sqlalchemy'
    DB_PG_RAW = 'postgres-raw'
    DB_CHOICES = (NONE, DB_PG_SA, DB_PG_RAW)

    EXAMPLE_MESSAGE_BOARD = 'message-board'
    EXAMPLE_CHOICES = (NONE, EXAMPLE_MESSAGE_BOARD)


class StartProject:
    def __init__(self, *,
                 path: str,
                 name: str,
                 template_engine: str=Options.TEMPLATE_ENG_JINJA2,
                 session: str=Options.SESSION_SECURE,
                 database: str=Options.NONE,
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

        self.files_created = 0
        self.ctx = {
            'name': name,
            'template_engine': self._choice_context(template_engine, Options.TEMPLATE_ENG_CHOICES),
            'session': self._choice_context(session, Options.SESSION_CHOICES),
            'database': self._choice_context(database, Options.DB_CHOICES),
            'example': self._choice_context(example, Options.EXAMPLE_CHOICES),
        }
        self.generate_directory(TEMPLATE_DIR)
        display_path = self.project_root.relative_to(Path('.').resolve())
        print('New aiohttp project "{name}" started at ./{path}'.format(name=name, path=display_path))

    def _choice_context(self, value, choices):
        return {'is_' + o.replace('-', '_'): value == o for o in choices}

    def generate_directory(self, p: Path):
        for pp in p.iterdir():
            if pp.is_dir():
                self.generate_directory(pp)
            elif pp.is_file() and pp.suffix:
                self.generate_file(pp)

    def generate_file(self, p: Path):
        try:
            template = Template(p.read_text())
            text = template.render(**self.ctx)
        except TemplateError as e:
            raise TemplateError('error in {}'.format(p)) from e
        text = text.strip('\n\t ')
        if not text:
            # empty files don't get created
            return

        if p.name == 'requirements.txt':
            packages = {p.strip() for p in text.split('\n') if p.strip()}
            text = '\n'.join(sorted(packages))
        elif p.suffix == '.py':
            # helpful when debugging: print(text.replace(' ', '·').replace('\n', '⏎\n'))
            for regex, repl in PY_REGEXES:
                text = regex.sub(repl, text)

        # re-add a trailing newline accounting for newlines added by PY_REGEXES
        text = re.sub('\n*$', '\n', text)
        new_path = self.project_root / p.relative_to(self.template_dir)
        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_text(text)
