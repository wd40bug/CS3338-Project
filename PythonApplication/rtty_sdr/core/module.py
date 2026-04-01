from typing import Protocol, Mapping, Type, Any

class Module(Protocol):
    topics: Mapping[str, Type[Any]]
    def run(self) -> None:
        ...
