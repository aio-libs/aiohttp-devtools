import os
from importlib.machinery import SourceFileLoader
from pathlib import Path
from setuptools import setup

THIS_DIR = Path(__file__).resolve().parent
long_description = THIS_DIR.joinpath('README.rst').read_text()

# avoid loading the package before requirements are installed:
version = SourceFileLoader('version', 'aiohttp_devtools/version.py').load_module()

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
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Unix',
        'Operating System :: POSIX :: Linux',
        'Environment :: MacOS X',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Internet',
        'Framework :: AsyncIO',
    ],
    author='Samuel Colvin',
    author_email='s@muelcolvin.com',
    url='https://github.com/aio-libs/aiohttp-devtools',
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
        'aiohttp>=3.0.1',
        'aiohttp_debugtoolbar>=0.4.0',
        'click>=6.6',
        'isort>=4.3.3',
        'Jinja2>=2.10',
        'watchgod>=0.0.3',
    ],
    python_requires='>=3.5',
)
