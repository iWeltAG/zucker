from enum import Enum
from typing import Protocol, runtime_checkable

from ..utils import JsonMapping


@runtime_checkable
class GenericFilter(Protocol):
    def build_filter(self) -> JsonMapping:
        ...


class Combinator(Enum):
    OR = "$or"
    AND = "$and"
