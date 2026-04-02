from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, Any
import msgspec


class TopicsRegistry:
    def __init__(self):
        self.__topics: dict[str, type[msgspec.Struct] | None] = {}

    def register(self, topic: str, type: type[msgspec.Struct] | None):
        assert not topic in self.__topics
        self.__topics[topic] = type

    def get(self, topic: str) -> type[msgspec.Struct] | None:
        assert topic in self.__topics, f"topic '{topic}' not registered"
        return self.__topics[topic]

    def validate(self, topic: str, payload: Any):
        if not topic in self.__topics:
            raise ValueError(f"No type registered for topic: {topic}")

        expected_type: Final[type[msgspec.Struct] | None] = self.__topics[topic]
        if expected_type is None:
            assert payload is None, f"Topic '{topic}' must have a payload of None"
            return
        
        assert isinstance(payload, expected_type), (
            f"Validation failed for {topic}: expected {expected_type}, "
            f"got {type(payload)}"
        )

    @property
    def TOPICS(self) -> MappingProxyType:
        return MappingProxyType(self.__topics)
