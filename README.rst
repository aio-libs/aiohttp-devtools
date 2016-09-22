aiohttp-devtools
================

|Build Status| |Coverage| |pypi| |license|

Dev tools for `aiohttp`_.

**Work in progress - not ready for use in the wild.**

Core Features
-------------

* a runserver command, roughly equivalent to https://github.com/samuelcolvin/aiohttp_runserver
* debug toolbar, roughly https://github.com/aio-libs/aiohttp_debugtoolbar
* a cookie cutter command to create a new bare bones aiohttp app similar to django's "startproject".
* an easy way to call management processes like creating or resetting a db.

Requirements
------------

* tightly coupled with aiohttp so there's no friction between versions
* this package shouldn't be required to run your app in production or to test it.
* extremely easy to get started with, should work wherever python works. I guess this requires testing on windows :-(.


.. |Build Status| image:: https://travis-ci.org/samuelcolvin/aiohttp-devtools.svg?branch=master
   :target: https://travis-ci.org/samuelcolvin/aiohttp-devtools
.. |Coverage| image:: https://codecov.io/gh/samuelcolvin/aiohttp-devtools/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/samuelcolvin/aiohttp-devtools
.. |pypi| image:: https://img.shields.io/pypi/v/aiohttp-devtools.svg
   :target: https://pypi.python.org/pypi/aiohttp-devtools
.. |license| image:: https://img.shields.io/pypi/l/aiohttp-devtools.svg
   :target: https://github.com/samuelcolvin/aiohttp-devtools
.. _aiohttp: http://aiohttp.readthedocs.io/en/stable/

