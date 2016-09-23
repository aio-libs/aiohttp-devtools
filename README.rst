aiohttp-devtools
================

|Build Status| |Coverage| |pypi| |license|

Dev tools for `aiohttp`_.

**Work in progress - not ready for use in the wild.**

Core Features
-------------

* ``runserver`` command including debug toolbar using `aiohttp debugtoolbar`_.
* ``start`` command to create a new bare bones aiohttp app similar to django's "startproject". Options:

  * **template engine**: none or either `aiohttp_jinja2`_.
  * **sessions**: none or secure or redis session from `aiohttp_session`_.
  * **database**: none or postgres using `aiopg`_ (eg. raw or using sqlalchemy), potentially other databases to follow.

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
.. _aiohttp debugtoolbar: https://github.com/aio-libs/aiohttp_debugtoolbar
.. _aiohttp_jinja2: https://github.com/aio-libs/aiohttp_jinja2
.. _aiohttp_session: https://aiohttp-session.readthedocs.io/en/latest/
.. _aiopg: https://aiopg.readthedocs.io/en/latest/
