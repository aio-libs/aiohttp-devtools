from aiohttp_devtools.start import StartProject


def test_start_simple(tmpworkdir):
    StartProject(path=str(tmpworkdir), name='foobar')
    assert {p.basename for p in tmpworkdir.listdir()} == {
        'app',
        'Makefile',
        'requirements.txt'
        'README.md',
        'settings.yml',
        'setup.cfg',
        'static',
        'tests',
    }
