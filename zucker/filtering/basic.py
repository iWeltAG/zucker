from __future__ import annotations

from abc import ABC
from numbers import Number
from typing import Generic

from ..utils import ApiType
from .combining import FilterSet
from .types import Combinator


class BasicFilter(ABC):
    """This is the most basic sort of filter - it checks if some specific field matches
    a condition.

    Subclasses of this type determine the exact condition that is tested (and how that
    condition is mapped to Sugar's API syntax). These filters can be combined with the
    ``&`` and ``|`` operators to create more complex filter sets.
    """

    def __init__(self, field_name: str, filters):
        self.field_name = field_name
        self.filters = filters

    def __or__(self, other):
        if isinstance(other, BasicFilter):
            return FilterSet(Combinator.OR, self, other)
        return NotImplemented

    def __and__(self, other):
        if isinstance(other, BasicFilter):
            return FilterSet(Combinator.AND, self, other)
        return NotImplemented

    @property
    def operator(self) -> str:
        raise NotImplementedError(
            "subclasses of BasicFilter must implement the operator property"
        )

    @property
    def filter_value(self):
        return self.filters

    def build_filter(self) -> dict:
        return {self.field_name: {self.operator: self.filter_value}}


class NegatableFilter(BasicFilter, ABC):
    def __invert__(self) -> NegatableFilter:
        raise NotImplementedError(
            "subclasses of NegatableFilter must implement the __invert__ protocol"
        )


class ValuesFilter(Generic[ApiType], NegatableFilter):
    """Basic filter that checks if the field exactly matches specified values.

    The constructor takes a field name and at least one value to test for. When one
    value is given, an equality check (using ``$equals`` in the Sugar API) will be
    produced. If more then one value is provided, it will switch to the ``$in``
    operator, which allows checking for multiple accepted values.

    This filter can be negated using the ``~`` operator.
    """

    def __init__(self, field_name: str, *filters: ApiType):
        if any(not isinstance(item, str) for item in filters):
            # TODO This doesn't currently match the type defintion above.
            raise TypeError("values for a value filter must strings")
        if len(filters) == 0:
            raise ValueError("did not provide any values for a value filter")

        self.negated = False

        super().__init__(field_name, list(filters))

    def __invert__(self) -> ValuesFilter:
        result = ValuesFilter(self.field_name, *self.filters)
        result.negated = not self.negated
        return result

    @property
    def operator(self) -> str:
        if len(self.filters) == 1:
            return "$not_equals" if self.negated else "$equals"
        else:
            return "$not_in" if self.negated else "$in"

    @property
    def filter_value(self):
        return self.filters[0] if len(self.filters) == 1 else self.filters


class NullishFilter(NegatableFilter):
    """Basic filter that checks if the field is None (or ``null`` in Sugar).

    This filter can be negated using the ``~`` operator.
    """

    def __init__(self, field_name: str):
        super().__init__(field_name, None)

        self.negated = False

    def __invert__(self) -> NullishFilter:
        result = NullishFilter(self.field_name)
        result.negated = not self.negated
        return result

    @property
    def operator(self) -> str:
        return "$not_null" if self.negated else "$is_null"


class StringFilter(BasicFilter, ABC):
    def __init__(self, field_name: str, value: str):
        if not isinstance(value, str):
            raise TypeError(
                f"string filters are only applicable for strings, got {type(value)!r}"
            )
        if len(value) == 0:
            raise ValueError("cannot filter for empty strings")

        super().__init__(field_name, value)


class StringStartsFilter(StringFilter):
    """Basic filter that checks if the string field starts with a given pattern."""

    @property
    def operator(self) -> str:
        return "$starts"


class StringEndsFilter(StringFilter):
    """Basic filter that checks if the string field ends with a given pattern."""

    @property
    def operator(self) -> str:
        return "$ends"


class StringContainsFilter(StringFilter):
    """Basic filter that checks if the string field contains a given pattern."""

    @property
    def operator(self) -> str:
        return "$ends"


class NumericFilter(NegatableFilter):
    def __init__(
        self,
        field_name: str,
        value: Number,
        *,
        greater: bool = False,
        equal: bool = False,
    ):
        if not isinstance(value, Number):
            raise TypeError(
                f"numeric filters only work with numbers, got {type(value)!r}"
            )

        super().__init__(field_name, value)
        self._greater = greater
        self._equal = equal

    def __invert__(self) -> NumericFilter:
        # When inverting,
        #   >  becomes <=
        #   >= becomes <
        #   <  becomes >=
        #   <= becomes >
        return NumericFilter(
            self.field_name,
            self.filters,
            greater=not self._greater,
            equal=not self._equal,
        )

    @property
    def operator(self) -> str:
        # Choose one of $gt, $gte, $lt and $lte.
        return f"${'gt' if self._greater else 'lt'}{'e' if self._equal else ''}"
