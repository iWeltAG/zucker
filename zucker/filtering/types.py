from enum import Enum
from typing import Protocol, runtime_checkable


@runtime_checkable
class GenericFilter(Protocol):
    def build_filter(self) -> dict:
        ...


class Combinator(Enum):
    OR = "$or"
    AND = "$and"
