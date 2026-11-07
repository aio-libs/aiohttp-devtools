import logging
import sys
from asyncio import Future
from multiprocessing import set_start_method
from pathlib import Path
from typing import Mapping, Union

import pytest

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


def mktree(root: Path, tree: FileTree) -> None:
    """Create a tree of files from a dictionary of name > content lookups."""
    for name, content in tree.items():
        path = root / name
        if isinstance(content, str):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        else:
            path.mkdir(parents=True)
            mktree(path, content)


@pytest.fixture(autouse=True)
def reset_start_method() -> None:
    """Allow runserver() to set the multiprocessing start method in forked tests.

    pytest-forked runs forked tests in a multiprocessing child process, which fixes the start method
    for that process, so it needs resetting before runserver() can set it to "spawn".
    """
    set_start_method(None, force=True)


@pytest.fixture
def tmpworkdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary directory and make it the working directory for the test."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


class SmartCaplog:
    """Captured log records, formatted as ``<logger name> <level>: <message>`` lines."""

    _formatter = logging.Formatter("%(name)s %(levelname)s: %(message)s")

    def __init__(self, caplog: pytest.LogCaptureFixture):
        self._caplog = caplog

    @property
    def log(self) -> str:
        return "".join(self._formatter.format(record) + "\n" for record in self._caplog.records)

    def __contains__(self, item: str) -> bool:
        return item in self.log

    def __eq__(self, other: object) -> bool:
        return self.log == other

    def __str__(self) -> str:
        return self.log

    def __repr__(self) -> str:
        return "<SmartCaplog: {!r}>".format(self.log)


@pytest.fixture
def smart_caplog(caplog: pytest.LogCaptureFixture) -> SmartCaplog:
    """Capture logs from all loggers at INFO level and above."""
    caplog.set_level(logging.INFO)
    return SmartCaplog(caplog)


def create_future(result=None):
    f: Future[None] = Future()
    f.set_result(result)
    return f
