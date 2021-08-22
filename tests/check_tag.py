#!/usr/bin/env python3
import os
import sys

from aiohttp_devtools import __version__

git_tag = os.getenv('TRAVIS_TAG')
if git_tag:
    if git_tag.lower().lstrip("v") != __version__:
        m = '✖ "TRAVIS_TAG" environment variable does not match package version: "{}" vs. "{}"'
        print(m.format(git_tag, __version__))
        sys.exit(1)
    else:
        m = '✓ "TRAVIS_TAG" environment variable matches package version: "{}" vs. "{}"'
        print(m.format(git_tag, __version__))
else:
    print('✓ "TRAVIS_TAG" not defined')
