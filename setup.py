import os
from importlib.machinery import SourceFileLoader
from pathlib import Path
from setuptools import setup

THIS_DIR = Path(__file__).resolve().parent
long_description = THIS_DIR.joinpath('README.rst').read_text()

# avoid loading the package before requirements are installed:
version = SourceFileLoader('version', 'aiohttp_devtools/version.py').load_module()


def check_livereload_js():
    import hashlib
    live_reload_221_hash = 'a451e4d39b8d7ef62d380d07742b782f'
    live_reload_221_url = 'https://raw.githubusercontent.com/livereload/livereload-js/v2.2.1/dist/livereload.js'

    path = THIS_DIR.joinpath('aiohttp_devtools/runserver/livereload.js')

    def check_path():
        with path.open('rb') as fr:
            file_hash = hashlib.md5(fr.read()).hexdigest()
        return file_hash == live_reload_221_hash

    if path.is_file():
        if check_path():
            return

    import urllib.request

    print('downloading livereload:\nurl:  {}\npath: {}'.format(live_reload_221_url, path))
    with urllib.request.urlopen(live_reload_221_url) as r:
        with path.open('wb') as fw:
            fw.write(r.read())

    if not check_path():
        raise RuntimeError('checksums do not match for {} after download'.format(path))

check_livereload_js()

package = THIS_DIR.joinpath('aiohttp_devtools/start')

start_package_data = []

for _root, _, files in os.walk(str(THIS_DIR.joinpath('aiohttp_devtools/start/template'))):
    root = Path(_root)
    for f in files:
        p = root / f
        start_package_data.append(str(p.relative_to(package)))

setup(
    name='aiohttp-devtools',
    version=str(version.VERSION),
    description='Dev tools for aiohttp',
    long_description=long_description,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Unix',  # FIXME: add all and test
        'Operating System :: POSIX :: Linux',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Internet',
    ],
    author='Samuel Colvin',
    author_email='s@muelcolvin.com',
    url='https://github.com/samuelcolvin/aiohttp-devtools',
    license='MIT',
    package_data={
        'aiohttp_devtools.runserver': ['livereload.js'],
        'aiohttp_devtools.start': start_package_data,
    },
    packages=[
        'aiohttp_devtools',
        'aiohttp_devtools.runserver',
        'aiohttp_devtools.start',
    ],
    zip_safe=True,
    entry_points="""
        [console_scripts]
        adev=aiohttp_devtools.cli:cli
        aiohttp-devtools=aiohttp_devtools.cli:cli
    """,
    install_requires=[
        'aiohttp>=1.1.6',
        'aiohttp-debugtoolbar>=0.1.3',
        'click>=6.6',
        'isort>=4.2.5',
        'Jinja2>=2.8',
        'trafaret>=0.7.5',
        'trafaret_config>=0.1.1',
        'watchdog>=0.8.3',
    ],
)
