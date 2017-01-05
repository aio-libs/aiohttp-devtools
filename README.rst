aiohttp-devtools
================

|Build Status| |Coverage| |pypi| |license|

Dev tools for `aiohttp`_.

**aiohttp-devtools** provides a number of tools useful when developing applications with aiohttp and associated
libraries.

Installation
------------

Requires **python 3.5** or **python 3.6**.

.. code:: shell

    pip install aiohttp-devtools

Usage
-----

The ``aiohttp-devtools`` CLI (and it's shorter alias ``adev``) Consists of three sub-commands:
`runserver`_, `serve`_ and `start`_.

runserver
~~~~~~~~~

Provides a simple local server for running your application while you're developing.

Usage is simply

.. code:: shell

    adev runserver <app-path>

``app-path`` can be a path to either a directory containing a recognized default file (``settings.y(a)ml``, ``app.py``
or ``main.py``) or to a specific file.

If a yaml file is found the "dev" dictionary in that file is used to populate settings for runserver,
if a python file is found it's run directly, the ``--app-factory`` option can be used to define which method is called,
if not supplied some default method names are tried.

``runserver`` has a couple of useful features:

* **livereload** will reload resources in the browser as your code changes without having to hit refresh, see `livereload_` for more details.
* **static files** are served separately from your main app (generally on ``8001`` while your app is on ``8000``) so you don't have to contaminate to serve static files you only need locally
* **debugtoolbar** is automatically enabled using `aiohttp debugtoolbar`_.

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

Is a "cookie cutter" command to create a new bare bones aiohttp app similar to django's "startproject".


Usage is simply

.. code:: shell

    adev start <path-to-directory-to-create-project-in>

You're then asked a bunch of questions about the the application you're about to create, you get to choose:

* **Template Engine** options are

  - **jinja** views are rendered using Jinja2 templates via `aiohttp_jinja2`_.
  - **none** views are rendered directly.

* **Session** options are

  - **secure** will implemented encrypted cookie sessions using `aiohttp_session`_.
  - **none** will mean no sessions

* **Database** options are:

  - **pg-sqlalchemy** will use postgresql via `aiopg`_ and the `SqlAlchemy`_ ORM.
  - **none** will use no database, persistence in examples is achieved by simply writing to file. This is a quick way to get started but is obviously not suitable for production use!

* **Example** the newly created app can include

  - **message board**: which demonstrates a little of aiohttp's usage. Messages and be added via posting to a form, are stored in the database and then displayed in a list, if available the session is used to pre-populate the user's name.
  - **none**: no example, just a single simple view is created.

For more options see ``adev start --help``, or just run ``adev start foobar`` and follow instructions.


Tutorial
--------

To demonstrate what adev can do let's walk through creating a new application:

First let's create a clean python environment to work in (it's assumed you've already got
**python 3.5**, **pip** and **virtualenv**) and install adev
(we might as well also install ``ipython`` as it alwasy comes in useful).

.. code:: shell

    mkdir my_new_app && cd my_new_app
    virtualenv -p /usr/bin/python3.5 env
    . env/bin/activate
    pip install aiohttp-devtools ipython


We're now ready to build our new application with `start`_, using the current directory ``.`` will put files where
we want them and will prompt adev to name the project ``my_new_app`` after the current directory.

We're going to explicitly choose no database here to make, this tutorial easier but you can remove that option
and choose to use a proper database if you like.

You can just hit return to choose the default for all the option options.


.. code:: shell

    adev start . --database none

That's it your, app is now created.

If you went of piste and choose to use a database you'll need to edit ``settings.yml`` to configure connection settings.

Before you can run your app you'll need to install the other requirements, luckily they've already been listed in
``./requirements.txt``, to install simply run

.. code:: shell

    pip install -r requirements.txt

You can then run your app with just

.. code:: shell

    adev runserver .

With that:

* your app should be being served at ``localhost:8000`` (you can go and play with it in a browser).
* Your static files are being served at ``localhost:8001``, adev has supplied configured your app to know that so it should be rendering properly.
* any changes to your app's code (``*.py`` files) should cause the server to reload, changes to any files (``*.py``, ``*.jinja``, ``*.js`` etc.) will cause livereload to prompt your browser to reload the required pages.

**That's it, go develop.**

.. |Build Status| image:: https://travis-ci.org/samuelcolvin/aiohttp-devtools.svg?branch=master
   :target: https://travis-ci.org/samuelcolvin/aiohttp-devtools
.. |Coverage| image:: https://codecov.io/gh/samuelcolvin/aiohttp-devtools/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/samuelcolvin/aiohttp-devtools
.. |pypi| image:: https://img.shields.io/pypi/v/aiohttp-devtools.svg
   :target: https://pypi.python.org/pypi/aiohttp-devtools
.. |license| image:: https://img.shields.io/pypi/l/aiohttp-devtools.svg
   :target: https://github.com/samuelcolvin/aiohttp-devtools
.. _livereload: https://github.com/livereload/livereload-js
.. _aiohttp: http://aiohttp.readthedocs.io/en/stable/
.. _aiohttp debugtoolbar: https://github.com/aio-libs/aiohttp_debugtoolbar
.. _aiohttp_jinja2: https://github.com/aio-libs/aiohttp_jinja2
.. _aiohttp_session: https://aiohttp-session.readthedocs.io/en/latest/
.. _aiopg: https://aiopg.readthedocs.io/en/latest/
.. _SqlAlchemy: http://www.sqlalchemy.org/
