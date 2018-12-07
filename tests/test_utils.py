from aiohttp_devtools.runserver.utils import MutableValue


def test_mutable_value():
    v = MutableValue('foo')
    assert len(v) == 3
    assert repr(v) == "'foo'"
    assert str(v) == 'foo'
    assert bool(v)
    assert v == 'foo'
    assert v + 'more' == 'foomore'
    assert v.startswith('f')

    v.change('bar')
    assert v == 'bar'
