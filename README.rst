aiohttp-devtools
================

|Coverage| |pypi| |license|

Dev tools for `aiohttp`_.

**aiohttp-devtools** provides a number of tools useful when developing applications with aiohttp and associated
libraries.

Installation
------------

.. code:: shell

    pip install aiohttp-devtools

Usage
-----

The ``aiohttp-devtools`` CLI (and it's shorter alias ``adev``) consist of two sub-commands:
`runserver`_ and `serve`_.

runserver
~~~~~~~~~

Provides a simple local server for running your application while you're developing.

Usage is simply

.. code:: shell

    adev runserver <app-path>

**Note:** ``adev runserver <app-path>`` will import the whole file, hence it doesn't work
with ``web.run_app(app)``. You can however use ``if __name__ == '__main__': web.run_app(app)``.

``app-path`` can be a path to either a directory containing a recognized default file (``app.py``
or ``main.py``) or to a specific file. The ``--app-factory`` option can be used to define which method is called
from the app path file, if not supplied some default method names are tried
(namely `app`, `app_factory`, `get_app` and `create_app`, which can be
variables, functions, or coroutines).

All ``runserver`` arguments can be set via environment variables.

``runserver`` has a few useful features:

* **livereload** will reload resources in the browser as your code changes without having to hit refresh, see `livereload`_ for more details.
* **static files** are served separately from your main app (generally on ``8001`` while your app is on ``8000``) so you don't have to contaminate your application to serve static files you only need locally.

For more options see ``adev runserver --help``.

serve
~~~~~

Similar to `runserver`_ except just serves static files.

Usage is simply

.. code:: shell

    adev serve <path-to-directory-to-serve>

Like ``runserver`` you get nice live reloading and access logs. For more options see ``adev serve --help``.

Tutorial
--------

To demonstrate what adev can do when combined with create-aio-app, let's walk through creating a new application:

First let's create a clean python environment to work in and install aiohttp-devtools and create-aio-app.

(it is assumed you've already got **python**, **pip** and **virtualenv** installed)

.. code:: shell

    mkdir my_new_app && cd my_new_app
    virtualenv -p `which python3` env
    . env/bin/activate
    pip install aiohttp-devtools create-aio-app


We're now ready to build our new application with ``create-aio-app`` and we'll name the
project ``my_new_app`` after the current directory.

We're going to explicitly choose no database here to make this tutorial easier, but you can remove that option
and choose to use a proper database if you like.

You can just hit return to choose the default for all the options.


.. code:: shell

    create-aio-app my_new_app --without-postgres

That's it, your app is now created. You might want to have a look through the local directory's file tree.

Before you can run your app you'll need to install the other requirements, luckily they've already been listed in
``requirements/development.txt`` by ``create-aio-app``, to install simply run

.. code:: shell

    pip install -r requirements/development.txt

You can then run your app with just:

.. code:: shell

    adev runserver

With that:

* your app should be being served at ``localhost:8000`` (you can go and play with it in a browser).
* Your static files are being served at ``localhost:8001``, adev has configured your app to know that so it should be rendering properly.
* any changes to your app's code (``.py`` files) should cause the server to reload, changes to any files
  (``.py`` as well as ``.jinja``, ``.js``, ``.css`` etc.) will cause livereload to prompt your browser to reload the required pages.

**That's it, go develop.**

.. |Coverage| image:: https://codecov.io/gh/aio-libs/aiohttp-devtools/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/aio-libs/aiohttp-devtools
.. |pypi| image:: https://img.shields.io/pypi/v/aiohttp-devtools.svg
   :target: https://pypi.python.org/pypi/aiohttp-devtools
.. |license| image:: https://img.shields.io/pypi/l/aiohttp-devtools.svg
   :target: https://github.com/aio-libs/aiohttp-devtools
.. _Changes.txt: /CHANGES.txt
.. _livereload: https://github.com/livereload/livereload-js
.. _aiohttp: http://aiohttp.readthedocs.io/en/stable/
