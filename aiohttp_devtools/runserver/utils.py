from typing import Any, Generic, Optional, TypeVar

_T = TypeVar("_T")


class MutableValue(Generic[_T]):
    """Used to avoid errors from aiohttp when the app context is modified."""

    __slots__ = ("value",)

    def __init__(self, value: Optional[_T] = None):
        self.value = value

    def change(self, new_value: _T) -> None:
        self.value = new_value

    def __len__(self) -> int:
        return len(self.value)  # type: ignore[arg-type]

    def __repr__(self) -> str:
        return repr(self.value)

    def __str__(self) -> str:
        return str(self.value)

    def __bool__(self) -> bool:
        return bool(self.value)

    def __eq__(self, other: object) -> "MutableValue[bool]":  # type: ignore[override]
        return MutableValue(self.value == other)

    def __add__(self, other: _T) -> _T:
        return self.value + other  # type: ignore[no-any-return, operator]

    def __getattr__(self, item: str) -> Any:
        return getattr(self.value, item)
