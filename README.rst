aiohttp-devtools
================

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

.. _aiohttp: http://aiohttp.readthedocs.io/en/stable/
