import base64
import os
import re
from pathlib import Path

from ..exceptions import AiohttpDevConfigError
from ..logs import main_logger as logger

THIS_DIR = Path(__file__).parent
TEMPLATE_DIR = THIS_DIR / 'template'


def check_dir_clean(d: Path):
    if d.exists():
        existing_paths = {p.name for p in d.iterdir()}
        new_paths = {p.name for p in TEMPLATE_DIR.iterdir()}
        conflicts = existing_paths & new_paths
        if conflicts:
            raise AiohttpDevConfigError('The path "{}" already has files/directories which would conflict '
                                        'with the new project: {}'.format(d, ', '.join(sorted(conflicts))))


class StartProject:
    def __init__(self, *, path: str, name: str, template_dir: Path = TEMPLATE_DIR) -> None:
        self.project_root = Path(path)
        self.template_dir = template_dir
        check_dir_clean(self.project_root)

        try:
            display_path = self.project_root.relative_to(Path('.').resolve())
        except ValueError:
            display_path = self.project_root

        logger.info('Starting new aiohttp project "%s" at "%s"', name, display_path)
        self.ctx = {
            'name': name,
            'cookie_name': re.sub(r'[^\w_]', '', re.sub(r'[.-]', '_', name)),
            'auth_key': base64.urlsafe_b64encode(os.urandom(32)).decode(),
        }
        self.ctx_regex = re.compile(r'\{\{ ?(%s) ?\}\}' % '|'.join(self.ctx.keys()))
        self.files_created = 0
        self.generate_directory(TEMPLATE_DIR)
        logger.info('project created, %d files generated', self.files_created)

    def generate_directory(self, p: Path):
        for pp in p.iterdir():
            if pp.is_dir():
                self.generate_directory(pp)
            else:
                assert pp.is_file()
                if not pp.name.endswith('.pyc'):
                    self.generate_file(pp)

    def generate_file(self, p: Path):
        text = p.read_text()
        new_path = self.project_root / p.relative_to(self.template_dir)
        logger.debug('creating "%s"', new_path)

        if p.name == 'settings.py':
            text = self.ctx_regex.sub(self.ctx_replace, text)

        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_text(text)
        self.files_created += 1

    def ctx_replace(self, m):
        return self.ctx[m.group(1)]
