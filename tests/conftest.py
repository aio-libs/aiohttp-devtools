import io
import logging
import os
import re
from copy import copy

import pytest
from py._path.local import LocalPath


def pytest_addoption(parser):
    parser.addoption('--fast', action='store_true', help="don't run slow tests")


@pytest.yield_fixture
def tmpworkdir(tmpdir):
    """
    Create a temporary working working directory.
    """
    cwd = os.getcwd()
    os.chdir(tmpdir.strpath)

    yield tmpdir

    os.chdir(cwd)


def mktree(lp: LocalPath, d):
    """
    Create a tree of files from a dictionary of name > content lookups.
    """
    for name, content in d.items():
        _lp = copy(lp)

        parts = list(filter(bool, name.split('/')))
        for part in parts[:-1]:
            _lp = _lp.mkdir(part)
        _lp = _lp.join(parts[-1])

        if isinstance(content, dict):
            _lp.mkdir()
            mktree(_lp, content)
        else:
            _lp.write(content)


def gettree(lp: LocalPath, max_len=80):
    """
    Get a dict representing the file tree for a directory
    """
    assert lp.check()
    if lp.isdir():
        return {df.basename: gettree(df) for df in lp.listdir()}
    elif lp.isfile():
        content = lp.read_text('utf8')
        if max_len and len(content) > max_len:
            content = content[:max_len - 3] + '...'
        return content
    else:
        raise RuntimeError('not directory or file: {}'.format(lp))


class StreamLog:
    """
    Log stream object which allows one or more logs to be captured and tested.
    """
    def __init__(self):
        self.handler = None
        self.stream = io.StringIO()
        self.handler = logging.StreamHandler(stream=self.stream)
        self.loggers = []
        self.set_loggers()

    def set_loggers(self, *log_names, level=logging.INFO, fmt='%(name)s: %(message)s'):
        if self.loggers:
            self.finish()
        log_names = log_names or ('',)
        self.loggers = [logging.getLogger(log_name) for log_name in log_names]
        self.handler.setFormatter(logging.Formatter(fmt))
        for logger in self.loggers:
            logger.disabled = False
            logger.addHandler(self.handler)
        self.set_level(level)

    def set_level(self, level):
        for logger in self.loggers:
            logger.setLevel(level)

    @classmethod
    def set_different_level(cls, **levels):
        for log_name, level in levels.items():
            logger = logging.getLogger(log_name)
            logger.setLevel(level)

    @property
    def log(self):
        self.stream.seek(0)
        return self.stream.read()

    def finish(self):
        for logger in self.loggers:
            logger.removeHandler(self.handler)

    def __call__(self, *normalisers):
        log = str(self)
        for pattern, repl in normalisers:
            log = re.sub(pattern, repl, log)
        return log

    def __eq__(self, other):
        return self.log == other

    def __contains__(self, item):
        return item in self.log

    def __str__(self):
        return self.log

    def __repr__(self):
        return '< caplog: {!r}>'.format(self.log)


@pytest.yield_fixture
def caplog():
    """
    Similar to pytest's "capsys" except logs are captured not stdout and stderr
    See StreamLog for details on configuration and tests for examples of usage.
    """
    stream_log = StreamLog()

    yield stream_log

    stream_log.finish()
