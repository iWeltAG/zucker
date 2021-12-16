from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Union

from ..utils import JsonMapping
from .types import Combinator, GenericFilter

FilterOrMapping = Union[GenericFilter, JsonMapping]


class FilterSet:
    def __init__(
        self,
        combinator: Combinator,
        *given_parts: Union[FilterOrMapping, None],
    ):
        self.combinator = combinator
        self._parts = list(given_parts)

        index = 0
        while index < len(self._parts):
            part = self._parts[index]

            if part is None:
                del self._parts[index]
                continue

            if not isinstance(part, (GenericFilter, Mapping)):
                raise TypeError(
                    f"FilterSet parts must be either dictionaries or generic filter "
                    f"compatible objects (like other FilterSets), got {type(part)!r}"
                )

            # Merge together this filterset and the provided one in these three cases:
            # 1) The current and the new filterset have the same combinator. This will
            #    convert constructs like this:
            #      (A or B or (C or (D or E)))
            #    into something flatter like this:
            #      (A or B or C or D or E)
            # 2) The new filterset has at most one part. In that case, that part (if
            #    available) can be merged into this filterset without changing the
            #    output boolean expression:
            #      (A or (B) or C)
            #    becomes
            #      (A or B or C)
            # 3) The new filterset is the only part we currently have. This is the
            #    reverse condition of the last case. The only difference here is that we
            #    don't keep our own combinator but rather that of the new filterset.
            #    Something like this:
            #      (None or (A and B))
            #    will be extracted to:
            #      (A and B)
            if isinstance(part, FilterSet):
                # This variable checks for the third condition above.
                merge_other = all(
                    other_part is None or other_part is part
                    for other_part in self._parts
                )
                if part.combinator == combinator or len(part._parts) < 2 or merge_other:
                    del self._parts[index]
                    self._parts[index:index] = part._parts
                    if merge_other:
                        self.combinator = part.combinator
                    continue

            # Render everything to an actual filter dictionary so that the whole
            # filterset remains immutable.
            if isinstance(part, GenericFilter):
                part = part.build_filter()

            assert isinstance(part, Mapping)

            self._parts[index] = copy.deepcopy(part)
            index += 1

    def __or__(self, other: FilterOrMapping) -> FilterSet:
        return self._combine(self, other, Combinator.OR)

    def __ror__(self, other: FilterOrMapping) -> FilterSet:
        return self._combine(other, self, Combinator.OR)

    def __and__(self, other: FilterOrMapping) -> FilterSet:
        return self._combine(self, other, Combinator.AND)

    def __rand__(self, other: FilterOrMapping) -> FilterSet:
        return self._combine(other, self, Combinator.AND)

    @staticmethod
    def _combine(
        first: FilterOrMapping, second: FilterOrMapping, combinator: Combinator
    ) -> FilterSet:
        if isinstance(first, (GenericFilter, Mapping)) and isinstance(
            second, (GenericFilter, Mapping)
        ):
            return FilterSet(combinator, first, second)
        return NotImplemented

    def build_filter(self) -> JsonMapping:
        return {
            self.combinator.value: [
                copy.deepcopy(
                    part.build_filter() if isinstance(part, GenericFilter) else part
                )
                for part in self._parts
            ]
        }
