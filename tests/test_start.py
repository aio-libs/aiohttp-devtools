from aiohttp_devtools.start import StartProject


def test_start_simple(tmpworkdir):
    StartProject(path=str(tmpworkdir), name='foobar')
    assert [p.basename for p in tmpworkdir.listdir()] == [
        'app',
        'tests',
        'settings.yml',
        'static',
        'setup.cfg',
        'README.md',
        'Makefile',
        'requirements.txt'
    ]
