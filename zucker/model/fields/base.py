from __future__ import annotations

import abc
import re
from numbers import Number
from typing import Awaitable  # noqa: F401
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    List,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
    overload,
)

from zucker.filtering import NegatableFilter, NullishFilter, NumericFilter, ValuesFilter
from zucker.utils import ApiType, JsonType

if TYPE_CHECKING:
    from zucker.model.module import AsyncModule, BaseModule, SyncModule, UnboundModule


NativeType = TypeVar("NativeType")
GetType = TypeVar("GetType")
ModuleType = TypeVar("ModuleType", bound="BaseModule")
SetType = TypeVar("SetType")
Self = TypeVar("Self", bound="Field[Any, Any]")
AnyModule = Union["SyncModule", "AsyncModule", "UnboundModule"]


class Field(Generic[ModuleType, GetType], abc.ABC):
    """Base class for all fields.

    This class accepts type variables which resemble the native type that is returned
    when the field accessed, for example as ``record.some_value`` where ``some_value``
    is the field instance. The generic arguments give the return type of that call,
    depending on whether the field is placed in a synchronous or an asynchronous
    module.
    """

    def __init__(self, api_name: Optional[str] = None):
        self._api_name = api_name
        self._name: Optional[str] = "test"
        # Check the name to make sure it's valid.
        self.name  # noqa
        self._name = None

    def __set_name__(self, owner: ModuleType, name: str) -> None:
        self._name = name
        # Check the name to make sure it's valid.
        self.name  # noqa

    @overload
    def __get__(self: Self, instance: ModuleType, owner: Type[BaseModule]) -> GetType:
        ...

    @overload
    def __get__(self: Self, instance: None, owner: Type[BaseModule]) -> Self:
        ...

    def __get__(
        self: Self,
        instance: Union[ModuleType, None],
        owner: Type[BaseModule],
    ) -> Union[GetType, Self]:
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
            return value  # type: ignore
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

    @abc.abstractmethod
    def _get_value(self, record: ModuleType) -> GetType:
        ...


class MutableField(
    Generic[ModuleType, GetType, SetType],
    Field[ModuleType, GetType],
    abc.ABC,
):
    """Base class for fields that are mutable.

    Being "mutable" means that users can not only read values, but also write (and save)
    new values for the field. Since setting could potentially take a different type,
    there are two generic arguments for this field. For example, a date field could
    return native date objects but additionally accept strings for setting.
    """

    def __set__(self, instance: ModuleType, value: SetType) -> None:
        from ..module import BaseModule

        if not isinstance(instance, BaseModule):
            raise AttributeError
        self._set_value(instance, value)

    @abc.abstractmethod
    def _set_value(self, record: ModuleType, value: SetType) -> None:
        ...


class ScalarField(
    Generic[NativeType, ApiType],
    Field[AnyModule, NativeType],
    abc.ABC,
):
    """Scalar fields are fields that also support some basic filtering operations.

    :param validators: Validators can be provided to make sure that data meets
        specific requirements. These will be checked both for incoming values from
        the server and for any value that is set on the field, before writing
        changes. A validator may either be a function or a regular expression
        object. The former will be called with the value to be checked as the single
        argument and should raise a :exc:`ValueError` when validation fails. The
        latter will pass the check if the entire value matches the provided regular
        expression.

    .. note::
        A few notes to keep in mind when using validators:

        1. The default strategy for validating regular expressions will coerce the incoming type to a string. That means that -- for example -- the number ``0xff`` *will* match the expression ``2..``, because the string representation is ``255``.
        2. Validators are always evaluated on the api data type. That means that they are run *after* serializing any user input.
    """

    def __init__(
        self,
        api_name: Optional[str] = None,
        *,
        validators: Optional[
            Sequence[Union[re.Pattern[str], Callable[[ApiType], None]]]
        ] = None,
    ):
        super().__init__(api_name=api_name)

        self._validators: List[Callable[[ApiType], None]] = []
        for validator in validators or []:
            if isinstance(validator, re.Pattern):

                def validate(value: ApiType) -> None:
                    assert isinstance(validator, re.Pattern)
                    if not validator.fullmatch(str(value)):
                        raise ValueError(f"pattern did not match: {validator.pattern}")

                self._validators.append(validate)
            elif callable(validator):
                self._validators.append(validator)
            else:
                raise TypeError(
                    f"validators must be regular expression pattern objects or "
                    f"callables, got {type(validator)!r}"
                )

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
        for validate in self._validators:
            validate(raw_value)  # type: ignore
        return self.load_value(raw_value)

    @abc.abstractmethod
    def load_value(cls, raw_value: JsonType) -> NativeType:
        """Load a value from the API into a native data type.

        :param raw_value: Response from the API for this field. This will be a JSON
            primitive, which should either be returned as-is (where appropriate) or
            converted into a native Python data type.
        :returns: A Python data type for this field.
        """

    @abc.abstractmethod
    def serialize(cls, value: Union[NativeType, ApiType]) -> ApiType:
        """Serialize a native data type into something the API can take back for
        saving.

        This method also supports "serializing" api types. In this case implementors are
        advised to verify the input's validity and return it as-is.

        :param value: Native or API data type for this field.
        :returns: An API-compatible data type.
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
    MutableField[
        AnyModule,
        NativeType,
        # Setting is supported by both the API type and the native type.
        Union[NativeType, ApiType],
    ],
    abc.ABC,
):
    """Mutable version of :class:`ScalarField`."""

    def _set_value(self, record: BaseModule, value: Union[ApiType, NativeType]) -> None:
        raw_value = self.serialize(value)
        for validate in self._validators:
            validate(raw_value)
        record._updated_data[self.name] = raw_value


class NumericField(Generic[ApiType], ScalarField[ApiType, ApiType], abc.ABC):
    """Scalar field with filtering operators that produce a total ordering."""

    def __lt__(self, other: Number) -> NumericFilter:
        """Filter for values less than the specified scalar:

        >>> Person.age < 10
        """
        return NumericFilter(self.name, other, greater=False, equal=False)

    def __lte__(self, other: Number) -> NumericFilter:
        """Filter for values less than or equal to the specified scalar:

        >>> Person.age <= 18
        """
        return NumericFilter(self.name, other, greater=False, equal=True)

    def __gt__(self, other: Number) -> NumericFilter:
        """Filter for values less than the specified scalar:

        >>> Person.age > 60
        """
        return NumericFilter(self.name, other, greater=True, equal=False)

    def __gte__(self, other: Number) -> NumericFilter:
        """Filter for values greater than or equal to the specified scalar:

        >>> Person.age >= 21
        """
        return NumericFilter(self.name, other, greater=True, equal=True)


class MutableNumericField(
    Generic[ApiType],
    NumericField[ApiType],
    MutableScalarField[ApiType, ApiType],
    abc.ABC,
):
    """Mutable version of :class:`NumericField`."""
