import sys
from asyncio import Future
from functools import partial
from multiprocessing import set_start_method
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Mapping, Union

import pytest

if TYPE_CHECKING:
    import trustme

if sys.platform == "win32":
    forked = pytest.mark.skip(reason="Windows doesn't suport fork")
else:
    forked = pytest.mark.forked

if sys.platform == "linux":
    linux_forked = pytest.mark.forked
else:
    def linux_forked(func):
        return func

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


@pytest.fixture(autouse=True)
def reset_start_method() -> None:
    """Allow runserver() to set the multiprocessing start method in forked tests.

    pytest-forked runs forked tests in a multiprocessing child process, which fixes the start method
    for that process, so it needs resetting before runserver() can set it to "spawn".
    """
    set_start_method(None, force=True)


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
def tmpworkdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary directory and make it the working directory for the test."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def mktree(tmpworkdir: Path) -> Callable[[FileTree], None]:
    """Create a tree of files in the working directory from a dictionary of name > content lookups."""
    return partial(_mktree, tmpworkdir)


def create_future(result=None):
    f: Future[None] = Future()
    f.set_result(result)
    return f
