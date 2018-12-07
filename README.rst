aiohttp-devtools
================

|Travis Build Status| |AppVeyor Build Status| |Coverage| |pypi| |license|

Dev tools for `aiohttp`_.

(Note: ``aiohttp-devtools>=0.8`` only supports ``aiohttp>=3.0``, if you're using older aiohttp, please use
an older version of ``aiohttp-devtools``, see `History.rst`_ for details.)

**aiohttp-devtools** provides a number of tools useful when developing applications with aiohttp and associated
libraries.

Installation
------------

Requires **python 3.5** or **python 3.6**.

.. code:: shell

    pip install aiohttp-devtools

Usage
-----

The ``aiohttp-devtools`` CLI (and it's shorter alias ``adev``) consist of three sub-commands:
`runserver`_, `serve`_ and `start`_.

runserver
~~~~~~~~~

Provides a simple local server for running your application while you're developing.

Usage is simply

.. code:: shell

    adev runserver <app-path>

``app-path`` can be a path to either a directory containing a recognized default file (``app.py``
or ``main.py``) or to a specific file. The ``--app-factory`` option can be used to define which method is called
from the app path file, if not supplied some default method names are tried.

All ``runserver`` arguments can be set via environment variables, the `start`_ command creates a script
suitable for setting up your environment such that you can run the dev server with just ``adev runserver``.

``runserver`` has a few of useful features:

* **livereload** will reload resources in the browser as your code changes without having to hit refresh, see `livereload`_ for more details.
* **static files** are served separately from your main app (generally on ``8001`` while your app is on ``8000``) so you don't have to contaminate your application to serve static files you only need locally

For more options see ``adev runserver --help``.

serve
~~~~~

Similar to `runserver`_ except just serves static files.

Usage is simply

.. code:: shell

    adev serve <path-to-directory-to-serve>

Like ``runserver`` you get nice live reloading and access logs. For more options see ``adev serve --help``.

start
~~~~~

Creates a new bare bones aiohttp app similar to django's "startproject".


Usage is simply

.. code:: shell

    adev start <path-to-directory-to-create-project-in>

You're then asked a bunch of questions about the the application you're about to create, you get to choose:

* **Template Engine**, options are

  - **jinja** views are rendered using Jinja2 templates via `aiohttp_jinja2`_.
  - **none** views are rendered directly.

* **Session**, options are

  - **secure** will implemented encrypted cookie sessions using `aiohttp_session`_.
  - **none** - session are not implemented

* **Database**, options are:

  - **pg-sqlalchemy** will use postgresql via `aiopg`_ and the `SqlAlchemy`_ ORM.
  - **none** will use no database, persistence in examples is achieved by simply writing to file.
    This is a quick way to get started but is obviously not suitable for production use!

* **Example**, the newly created app can include some basic functionality

  - **message board**: which demonstrates a little of aiohttp's usage. Messages can be added via posting to a form,
    are stored in the database and then displayed in a list, if available the session is used to pre-populate the user's name.
  - **none**: no example, just a single simple view is created.

For more options see ``adev start --help``, or just run ``adev start foobar`` and follow instructions.


Tutorial
--------

To demonstrate what adev can do, let's walk through creating a new application:

First let's create a clean python environment to work in and install aiohttp-devtools.

(it is assumed you've already got **python 3.5**, **pip** and **virtualenv** installed)

.. code:: shell

    mkdir my_new_app && cd my_new_app
    virtualenv -p `which python3.7` env
    . env/bin/activate
    pip install aiohttp-devtools


We're now ready to build our new application with `start`_, using the current directory ``.`` will put files where
we want them and will prompt adev to name the project ``my_new_app`` after the current directory.

We're going to explicitly choose no database here to make, this tutorial easier but you can remove that option
and choose to use a proper database if you like.

You can just hit return to choose the default for all the options.


.. code:: shell

    adev start . --database none

That's it, your app is now created. You might want to have a look through the local directory's file tree.

Before you can run your app you'll need to install the other requirements, luckily they've already been listed in
``./requirements.txt`` by `start`_, to install simply run

.. code:: shell

    pip install -r requirements.txt

(If you went off-piste and choose to use a database you'll need to edit ``activate.settings.sh`` to configure
connection settings, then run ``make reset-database`` to create a database.)

You can then run your app with just:

.. code:: shell

    source activate.settings.sh
    adev runserver

`runserver`_ uses the environment variables set in ``activate.settings.sh`` to decide how to serve your app.

With that:

* your app should be being served at ``localhost:8000`` (you can go and play with it in a browser).
* Your static files are being served at ``localhost:8001``, adev has configured your app to know that so it should be rendering properly.
* any changes to your app's code (``.py`` files) should cause the server to reload, changes to any files
  (``.py`` as well as ``.jinja``, ``.js``, ``.css`` etc.) will cause livereload to prompt your browser to reload the required pages.

**That's it, go develop.**

.. |Travis Build Status| image:: https://travis-ci.com/aio-libs/aiohttp-devtools.svg?branch=master
   :target: https://travis-ci.com/aio-libs/aiohttp-devtools
   :alt: Travis status for master branch
.. |AppVeyor Build Status| image:: https://ci.appveyor.com/api/projects/status/abklub4k2spyutw7/branch/master?svg=true
   :target: https://ci.appveyor.com/project/aio-libs/aiohttp-devtools
   :alt: AppVeyor status for master branch
.. |Coverage| image:: https://codecov.io/gh/aio-libs/aiohttp-devtools/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/aio-libs/aiohttp-devtools
.. |pypi| image:: https://img.shields.io/pypi/v/aiohttp-devtools.svg
   :target: https://pypi.python.org/pypi/aiohttp-devtools
.. |license| image:: https://img.shields.io/pypi/l/aiohttp-devtools.svg
   :target: https://github.com/aio-libs/aiohttp-devtools
.. _History.rst: /HISTORY.rst
.. _livereload: https://github.com/livereload/livereload-js
.. _aiohttp: http://aiohttp.readthedocs.io/en/stable/
.. _aiohttp_jinja2: https://github.com/aio-libs/aiohttp_jinja2
.. _aiohttp_session: https://aiohttp-session.readthedocs.io/en/latest/
.. _aiopg: https://aiopg.readthedocs.io/en/latest/
.. _SqlAlchemy: http://www.sqlalchemy.org/
