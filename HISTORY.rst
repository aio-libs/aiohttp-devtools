.. :changelog:

History
-------

0.2.0 (TBD)
------------------
* allow "app_factory" to be just a plain ``aiohttp.Application`` (or a function creating an application as before)

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
