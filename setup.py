from importlib.machinery import SourceFileLoader
from pathlib import Path
from setuptools import setup

THIS_DIR = Path(__file__).resolve().parent
long_description = THIS_DIR.joinpath('README.rst').read_text()

# avoid loading the package before requirements are installed:
version = SourceFileLoader("__version__", "aiohttp_devtools/__init__.py").load_module()

name = 'aiohttp-devtools'
repo_slug = 'aio-libs/{}'.format(name)
repo_url = 'https://github.com/{}'.format(repo_slug)

setup(
    name=name,
    version=version.__version__,
    description='Dev tools for aiohttp',
    long_description=long_description,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        "Programming Language :: Python :: 3.11",
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
        'Operating System :: Unix',
        'Environment :: MacOS X',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Internet',
        'Framework :: AsyncIO',
    ],
    author='Samuel Colvin',
    author_email='s@muelcolvin.com',
    url=repo_url,
    project_urls={
        'CI: AppVeyor': 'https://ci.appveyor.com/project/{}'.format(repo_slug),
        'CI: Travis': 'https://travis-ci.com/{}'.format(repo_slug),
        'Coverage: codecov': 'https://codecov.io/github/{}'.format(repo_slug),
        'GitHub: issues': '{}/issues'.format(repo_url),
        'GitHub: repo': repo_url,
    },
    license='MIT',
    package_data={
        'aiohttp_devtools.runserver': ['livereload.js'],
    },
    packages=[
        'aiohttp_devtools',
        'aiohttp_devtools.runserver',
    ],
    zip_safe=True,
    entry_points="""
        [console_scripts]
        adev=aiohttp_devtools.cli:cli
        aiohttp-devtools=aiohttp_devtools.cli:cli
    """,
    install_requires=[
        "aiohttp>=3.9",
        'click>=6.6',
        'devtools>=0.6',
        'Pygments>=2.2.0',
        "watchfiles>=0.10"
    ],
    python_requires=">=3.8",
)
