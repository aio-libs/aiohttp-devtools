

class MutableValue:
    """
    Used to avoid warnings (and in future errors) from aiohttp when the app context is modified.
    """
    __slots__ = 'value',

    def __init__(self, value=None):
        self.value = value

    def change(self, new_value):
        self.value = new_value

    def __len__(self):
        return len(self.value)

    def __repr__(self):
        return repr(self.value)

    def __str__(self):
        return str(self.value)

    def __bool__(self):
        return bool(self.value)

    def __eq__(self, other):
        return MutableValue(self.value == other)

    def __add__(self, other):
        return self.value + other

    def __getattr__(self, item):
        return getattr(self.value, item)
