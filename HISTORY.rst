.. :changelog:

History
-------

0.13.1 (2019-06-19)
-------------------
* re-enable support for alternative loops, #238

0.13.0 (2019-05-21)
-------------------
* greatly simplify the ``start`` command, #233
* disable coloured output on windows, #234
* fix ``adev serve ...``, #235

0.12.0 (2019-02-20)
-------------------
* fix tests for python 3.7, #218
* fix tests for aiohttp >= 3.5, #223
* rebuild logging with coloured tracebacks and request & response details, #221

0.11.0 (2018-12-07)
-------------------
* use ``--root`` as base directory for watching if it's set, #209
* add ``MutableValue`` to avoid aiohttp warnings, #215
* improved logging including request time, #217
* remove ``aiohttp_debugtoolbar`` as a requirement, improve CI, #216
* uprev dependencies

0.10.4 (2018-11-19)
-------------------
* fix conflict with click checks that prevented the ``--root`` flag working properly, #206
* uprev dependencies

0.10.3 (2018-09-25)
-------------------
* remove ``loop`` argument from ``run_app()``, #206
* uprev dependencies

0.10.2 (2018-06-09)
-------------------
* fix path defining to work both for Unix and Windows

0.10.1 (2018-06-06)
-------------------
* fix logging with ``runserver`` #193

0.10.0 (2018-05-29)
-------------------
* allow async app factories #185
* uprev to aiohttp 3.2.0 min #187
* revert runserver to use a separate process #188

0.9.0 (2018-03-20)
------------------
* deep reload for for better auto-reloading #181

0.8.0 (2018-02-12)
------------------
* complete rewrite for aiohttp >= 3 stop using multiprocessing #173
* update required packages #171

0.7.1 (2018-02-01)
------------------
* set ``Access-Control-Allow-Origin`` for static files, #169

0.7.0 (2018-01-18)
------------------
* use ``static_root_url`` on with ``--static`` option #170
* fix ``unquote`` import #167

0.6.4 (2017-11-26)
------------------
* fix loop usage to work with uvloop, #158

0.6.3 (2017-10-20)
------------------
* add ``livereload.js`` to release package

0.6.2 (2017-10-19)
------------------
* fix loop pickling regression in #150 #154
* cleanup termination with uvloop #154

0.6.1 (2017-10-19)
------------------
* switch config order to support uvloop #150
* more lenient set_tty (to support pycharm) #152

0.6.0 (2017-10-18)
------------------
* switch from watchdog to watchgod #144
* allow use of ``pdb`` inside app #145
* support aiohttp 2.3.0 #148

0.5.0 (2017-07-01)
------------------
* set loop before running app check #96
* allow app factory with simpler signature ``app_factory()`` #96
* expose ``aiohttp_devtools.__version__`` #98
* add ``__main__.py`` to allow ``python -m aiohttp_devtools ...`` #99

0.4.1 (2017-06-03)
------------------
* numerous package upgrades
* fix typos

0.4.0 (2017-05-02)
------------------
* add support for remote host - #72
* add asyncio trove classifiers - #68

0.3.3 (2017-03-31)
------------------
* fix type for port and aux-port - #59
* allow empty response body - #56
* uprev numerous packages, nothing significant
* improve runserver shutdown logic
* db settings without message example - #53

0.3.2 (2017-03-22)
------------------
* fix ``prepare_database`` for fresh ``start`` projects

0.3.1 (2017-03-22)
------------------
* correct aiohttp version in ``start`` template

0.3.0 (2017-03-21)
------------------
* **breaking change**: v0.3.0 only supports ``aiohttp>=2.0.0``
* **breaking change**: ``runserver`` not longer works with ``settings.yml`` config files, environment variables
  are now used in it's place
* clean up config arguments
* refactoring to support aiohttp 2

0.2.1 (2017-03-16)
------------------
This will be the final version which supports ``aiohttp < 2``

* correct setup and readme links
* pin aiohttp version to ``<2.0``

0.2.0 (2017-02-19)
------------------
* allow "app_factory" to be just a plain ``aiohttp.Application`` (or a function creating an application as before)
* fix compatibility with aiohttp 2.0.0a - still not working fully with latest aiohttp

0.1.4 (2017-02-11)
------------------
* resolve conflicts with aiohttp 1.3.0
* test build matrix to test with all recent version of aiohttp and master
* dependency updates
* fix for ``fmt_size`` with size ``None``

0.1.3 (2017-01-18)
------------------
* add ``app.cleanup()`` to pre-checks
* add ``--pre-check/--no-pre-check`` flag

0.1.2 (2017-01-11)
------------------
* move to ``grablib`` for downloading ``livereload.js``
* update  aiohttp-session from 0.7.1 to 0.8.0 (#9)
* update aiopg from 0.12.0 to 0.13.0 (#11)
* update aiohttp-jinja2 from 0.8.0 to 0.13.0 (#12)
* fix formatting and typos in numerous commends and start's README
* fix template variable in ``requirements.txt``
* check tag matches ``version.VERSION`` before a release

0.1.1 (2017-01-06)
------------------
* fix template variables so ``settings.yml`` include db connection settings and ``requirements.txt`` is correct
* fix ``requirements.txt`` template to be compatible with pyup
* add basic help to readme
* allow environment variable substitution into settings

0.1.0 (2017-01-05)
------------------
First proper release.
