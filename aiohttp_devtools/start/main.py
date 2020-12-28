from pathlib import Path

from ..exceptions import AiohttpDevConfigError
from ..logs import main_logger as logger

THIS_DIR = Path(__file__).parent
TEMPLATE_DIR = THIS_DIR / 'demos' / 'demos'
DEMO_NAMES = tuple(d.name for d in TEMPLATE_DIR.iterdir() if d.is_dir())


def check_dir_clean(d: Path, demo: str):
    if d.exists():
        existing_paths = {p.name for p in d.iterdir()}
        demo_dir = TEMPLATE_DIR / demo
        new_paths = {p.name for p in demo_dir.iterdir()}
        conflicts = existing_paths & new_paths
        if conflicts:
            raise AiohttpDevConfigError('The path "{}" already has files/directories which would conflict '
                                        'with the new project: {}'.format(d, ', '.join(sorted(conflicts))))


class StartProject:
    def __init__(self, *, path: str, name: str, demo: str = "polls",
                 template_dir: Path = TEMPLATE_DIR) -> None:
        self.project_root = Path(path)
        self.template_dir = template_dir / demo
        check_dir_clean(self.project_root, demo)

        try:
            display_path = self.project_root.relative_to(Path('.').resolve())
        except ValueError:
            display_path = self.project_root

        logger.info('Starting new aiohttp project "%s" at "%s"', name, display_path)
        self.files_created = 0
        self.generate_directory(self.template_dir)
        logger.info('project created, %d files generated', self.files_created)
        logger.info('Install the required packages with `pip install -r requirements-dev.txt`')
        logger.info('Run your app during development with `adev runserver %s -s static`', name)

    def generate_directory(self, p: Path):
        for pp in p.iterdir():
            if pp.is_dir():
                self.generate_directory(pp)
            else:
                assert pp.is_file()
                if not pp.name.endswith('.pyc'):
                    self.generate_file(pp)

    def generate_file(self, p: Path):
        content = p.read_bytes()
        new_path = self.project_root / p.relative_to(self.template_dir)
        logger.debug('creating "%s"', new_path)

        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_bytes(content)
        self.files_created += 1
