import sys
from asyncio import Future
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterator, Mapping, Union

import pytest

if TYPE_CHECKING:
    import trustme

SIMPLE_APP = {
    'app.py': """\
from aiohttp import web


async def hello(request):
    return web.Response(text='hello world')

def create_app():
    app = web.Application()
    app.router.add_get('/', hello)
    return app"""
}

FileTree = Mapping[str, Union[str, "FileTree"]]


def _mktree(root: Path, tree: FileTree) -> None:
    for name, content in tree.items():
        path = root / name
        if isinstance(content, str):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        else:
            path.mkdir(parents=True)
            _mktree(path, content)


@pytest.fixture
def tls_certificate_authority() -> "trustme.CA":
    """Create a throwaway CA for the test, so the test certificates can never go stale."""
    if not TYPE_CHECKING:
        trustme = pytest.importorskip("trustme")
    return trustme.CA()


@pytest.fixture
def tls_certificate(tls_certificate_authority: "trustme.CA") -> "trustme.LeafCert":
    """Create a server certificate for localhost, signed by tls_certificate_authority."""
    return tls_certificate_authority.issue_cert("localhost", "127.0.0.1", "::1")


@pytest.fixture
def tmpworkdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Create a temporary directory and make it the working directory for the test.

    Importing an app adds the directory to sys.path and caches the app's modules in sys.modules.
    Both are undone afterwards, so that each test imports its own app.py.
    """
    monkeypatch.chdir(tmp_path)
    sys_path = sys.path.copy()
    sys_modules = set(sys.modules)
    yield tmp_path
    sys.path[:] = sys_path
    for name in sys.modules.keys() - sys_modules:
        module_file = getattr(sys.modules[name], "__file__", None)
        if module_file and Path(module_file).is_relative_to(tmp_path):
            del sys.modules[name]


@pytest.fixture
def mktree(tmpworkdir: Path) -> Callable[[FileTree], None]:
    """Create a tree of files in the working directory from a dictionary of name > content lookups."""
    return partial(_mktree, tmpworkdir)


def create_future(result=None):
    f: Future[None] = Future()
    f.set_result(result)
    return f
