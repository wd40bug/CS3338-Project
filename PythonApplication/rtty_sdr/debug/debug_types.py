from typing import Protocol, Self

class DebugCombineable(Protocol):
    @classmethod
    def combine(cls, debugs: list[Self]) -> Self:
        return cls.combine(debugs)
