from __future__ import annotations

import abc
from typing import Awaitable  # noqa: F401
from typing import TYPE_CHECKING, Any, Generic, Optional, Type, TypeVar, Union, overload

from zucker.filtering import NegatableFilter, NullishFilter, ValuesFilter
from zucker.utils import ApiType, JsonType

if TYPE_CHECKING:
    from zucker.model.module import AsyncModule, BaseModule, SyncModule, UnboundModule


NativeType = TypeVar("NativeType")
SyncGetType = TypeVar("SyncGetType")
AsyncGetType = TypeVar("AsyncGetType")
SetType = TypeVar("SetType")
Self = TypeVar("Self", bound="Field[Any, Awaitable[Any]]")


class Field(Generic[SyncGetType, AsyncGetType], abc.ABC):
    """Base class for all fields.

    This class accepts type variables which resemble the native type that is returned
    when the field accessed, for example as ``record.some_value`` where ``some_value``
    is the field instance. The generic arguments give the return type of that call,
    depending on whether the field is placed in a synchronous or an asynchronous
    module.
    """

    def __init__(self, api_name: Optional[str] = None, **kwargs):
        self._api_name = api_name
        self._name: Optional[str] = "test"
        # Check the name to make sure it's valid.
        self.name  # noqa
        self._name = None

    def __set_name__(self, owner: BaseModule, name: str) -> None:
        self._name = name
        # Check the name to make sure it's valid.
        self.name  # noqa

    @overload
    def __get__(
        self: Self, instance: SyncModule, owner: Type[BaseModule]
    ) -> SyncGetType:
        ...

    @overload
    def __get__(
        self: Self, instance: AsyncModule, owner: Type[BaseModule]
    ) -> AsyncGetType:
        ...

    @overload
    def __get__(
        self: Self, instance: UnboundModule, owner: Type[BaseModule]
    ) -> SyncGetType:
        ...

    @overload
    def __get__(self: Self, instance: None, owner: Type[BaseModule]) -> Self:
        ...

    def __get__(
        self: Self,
        instance: Union[SyncModule, AsyncModule, UnboundModule, None],
        owner: Type[BaseModule],
    ) -> Union[SyncGetType, AsyncGetType, Self]:
        from ..module import BaseModule

        if isinstance(instance, BaseModule):
            # Here, the field is accessed as a property on a record, like this:
            #   the_first_name = record.first_name
            # In this case, the actual field type determines which data is returned.
            value = self._get_value(instance)
            # This type is ignored because because MyPy cannot parse generic self
            # argument types and just flat-out ignores them currently. Hence,
            # self._get_value() is actually an Any (since self is a 'Self' which is
            # Field[Any] or some subtype).
            # See also: https://github.com/python/mypy/issues/2354
            return value  # type:ignore
        elif instance is None:
            # The other case is when the field gets referenced directly on the class,
            # for example when building queries:
            #   module.filter(Lead.name == "Apple")
            # Here we return the field itself again, because then we can build filters
            # and use other APIs from the class.
            return self

        else:
            raise AttributeError(
                f"Field() objects should only created inside bound modules - got "
                f"{instance!r}"
            )

    @property
    def name(self) -> str:
        if self._api_name is not None:
            result = self._api_name
        elif self._name is None:
            raise RuntimeError(
                "Could not retrieve the field's model name. Check for the correct "
                "Field() usage - otherwise this is a bug."
            )
        else:
            result = self._name

        if not isinstance(result, str):
            raise TypeError(f"field name must be a string, got {result!r}")
        if result == "" or " " in result:
            raise ValueError("field name may not be empty and must not contain spaces")

        return result

    @overload
    def _get_value(self, record: SyncModule) -> SyncGetType:
        ...

    @overload
    def _get_value(self, record: AsyncModule) -> AsyncGetType:
        ...

    @overload
    def _get_value(self, record: UnboundModule) -> SyncGetType:
        ...

    @abc.abstractmethod
    def _get_value(
        self, record: Union[SyncModule, AsyncModule, UnboundModule]
    ) -> Union[SyncGetType, AsyncGetType]:
        ...


class MutableField(
    Generic[SyncGetType, AsyncGetType, SetType],
    Field[SyncGetType, AsyncGetType],
    abc.ABC,
):
    """Base class for fields that are mutable.

    Being "mutable" means that users can not only read values, but also write (and save)
    new values for the field. Since setting could potentially take a different type,
    there are two generic arguments for this field. For example, a date field could
    return native date objects but additionally accept strings for setting.
    """

    def __set__(self, instance: BaseModule, value: SetType) -> None:
        from ..module import BaseModule

        if not isinstance(instance, BaseModule):
            raise AttributeError
        self._set_value(instance, value)

    @abc.abstractmethod
    def _set_value(self, record: BaseModule, value: SetType) -> None:
        ...


class ScalarField(Generic[NativeType, ApiType], Field[NativeType, NativeType], abc.ABC):
    """Scalar fields are fields that also support some basic filtering operations."""

    ##################################
    # Getting / setting field values #
    ##################################

    def _get_value(self, record: BaseModule) -> NativeType:
        raw_value = record.get_data(self.name)

        if raw_value is None:
            raise AttributeError(
                f"Trying to access an undefined field {self.name!r} in record "
                f"{type(record)!r}. Either add the field to the module "
                f"definition or check for the correct spelling."
            )
        return self.load_value(raw_value)

    @classmethod
    @abc.abstractmethod
    def load_value(cls, raw_value: JsonType) -> NativeType:
        """Load a value from the API into a native data type.

        :param raw_value: Response from the API for this field. This will be a JSON
            primitive, which should either be returned as-is (where appropriate) or
            converted into a native Python data type.
        :returns: A Python data type for this field.
        """

    @classmethod
    @abc.abstractmethod
    def serialize(cls, value: Union[NativeType, ApiType]) -> ApiType:
        """Serialize a native data type into something the API can take back for
        saving.

        Note: this method also supports "serializing" api types, which generally should
        just verify their validity and return them as-is.
        """

    ###################
    # Filter building #
    ###################

    def __eq__(  # type: ignore[override]
        self, other: Optional[Union[NativeType, ApiType]]
    ) -> NegatableFilter[Any]:
        """Filter for exact values of this field.

        Depending on type of the given value, this is is equivalent to one of the other
        filtering methods:

            >>> Person.name == "Ben" # Is the same as Person.name.values("Ben")
            >>> Person.age == 3 # Is the same as Person.age.values(3)
            >>> Person.supervisor == None # Is the same as Person.supervisor.null()
        """
        if other is None:
            return self.null()
        else:
            return self.values(other)

    def __ne__(  # type: ignore[override]
        self, other: Optional[Union[NativeType, ApiType]]
    ) -> NegatableFilter[Any]:
        """Inverse of the ``==`` filter operator.

        Use the ``!=`` operator to exclude specific values:

            >>> Person.name != "Ben" # Is the same as ~(Person.name.values("Ben"))
            >>> Person.supervisor != None # Is the same as ~(Person.supervisor.null())
        """
        return ~(self.__eq__(other))

    def values(self, *values: Union[NativeType, ApiType]) -> ValuesFilter[ApiType]:
        """Filter for exact values of this field.

        Most basic use for this filter is finding objects by value. The filter

            >>> Person.name.values("Ben")

        will return objects who's name is 'Ben'.

        This filter takes one or more arguments. It matches entries where this set
        directly contains the field's value, for example:

            >>> Person.name.values("Paul", "Spencer")

        will match objects who's name is either 'Paul' or 'Spencer'.

        Inverting this filter yields a 'not-equal' filter, for example:

            >>> ~Person.name.values("Mike")

        This query will match all objects where the name is not equal to 'Mike'.

        The above examples are also available as a shorthand through the equals
        operator (although you can only check for a single value here):

            >>> Person.name == "Ben"
            >>> Person.name != "Ben"
        """
        return ValuesFilter(
            self.name, *tuple(self.serialize(raw_value) for raw_value in values)
        )

    def null(self) -> NullishFilter:
        """Filter for whether the field is null.

        Use the filter like this:

            >>> Person.employer.null()

        This will return objects where the 'employer' field is not set.

        To find only objects where a field is explicitly not null, invert the filter:

            >>> ~Person.employer.null()

        As a shorthand, you can also use the equals operator for the above examples:

            >>> Person.employer == None
            >>> Person.employer != None
        """
        return NullishFilter(self.name)


class MutableScalarField(
    Generic[NativeType, ApiType],
    ScalarField[NativeType, ApiType],
    # Setting is supported by both the API type and the native type.
    MutableField[NativeType, NativeType, Union[NativeType, ApiType]],
    abc.ABC,
):
    def _set_value(self, record: BaseModule, value: Union[ApiType, NativeType]) -> None:
        raw_value = self.serialize(value)
        record._updated_data[self.name] = raw_value
