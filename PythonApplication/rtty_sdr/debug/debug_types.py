from typing import Protocol, Self

class DebugCombineable(Protocol):
    @classmethod
    def combine(cls, debugs: list[Self]) -> Self:
        ...

    @classmethod
    def default(cls) -> Self:
        ...

class DebugSliceable(DebugCombineable):
    def __getitem__(self, key: slice | int) -> Self:
        ...

    def __len__(self) -> int:
        ...
