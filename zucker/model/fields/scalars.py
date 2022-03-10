from __future__ import annotations

import enum  # noqa: F401
from typing import Any, Generic, Optional, Type, TypeVar, Union, cast
from urllib import parse as urllib_parse
from uuid import UUID

from zucker import filtering
from zucker.codegen.inspection import field_for_metadata
from zucker.utils import JsonType

from .base import MutableNumericField, MutableScalarField, ScalarField

__all__ = [
    "BooleanField",
    "FloatField",
    "IdField",
    "IntegerField",
    "LegacyEmailField",
    "StringField",
    "URLField",
    "EnumField",
]


# See this page for a reference of field types:
# https://support.sugarcrm.com/Documentation/Sugar_Versions/11.2/Pro/Administration_Guide/Developer_Tools/Studio/Fields/


@field_for_metadata.register(metadata_attributes=dict(name="id"), require_db=True)
@field_for_metadata.register(metadata_attributes=dict(type="id"), require_db=True)
class IdField(ScalarField[UUID, str]):
    """Immutable field for accessing record IDs.

    An instance of this field is automatically created for every module. Manually
    creating fields of this type should only be necessary for referencing links. In
    Python, IDs are represented by :class:`UUID` objects.
    """

    @classmethod
    def load_value(cls, raw_value: JsonType) -> UUID:
        if not isinstance(raw_value, str):
            raise TypeError(f"IDs must be strings, got {type(raw_value)!r}")
        return UUID(raw_value)

    @classmethod
    def serialize(cls, value: Union[UUID, str]) -> str:
        if isinstance(value, str):
            # "Load" the value to check if it is a valid ID.
            value = cls.load_value(value)
        return str(value)


@field_for_metadata.register(metadata_attributes=dict(type="url"), require_db=True)
class URLField(MutableScalarField[urllib_parse.ParseResult, str]):
    """Mutable string field for URLs.

    This should be used for database columns of type ``url``. URLs will be decoded and
    returned as an instance of :class:`urllib.parse.ParseResult`, which contains the
    parsed components of the URL. To get a string, call ``str()`` with the result
    object.
    """

    @staticmethod
    def load_value(raw_value: JsonType) -> urllib_parse.ParseResult:
        if not isinstance(raw_value, str):
            raise TypeError(
                f"URL field must be populated with a string - got "
                f"{type(raw_value)!r}"
            )
        return urllib_parse.urlparse(raw_value)

    @staticmethod
    def serialize(value: Union[urllib_parse.ParseResult, str]) -> str:
        parsed_value = (
            value
            if isinstance(value, urllib_parse.ParseResult)
            else URLField.load_value(value)
        )
        return parsed_value.geturl()


# Note: this field needs to be registered before StringField because of the matching
# order here:
@field_for_metadata.register(metadata_attributes=dict(name="email1"), require_db=True)
@field_for_metadata.register(metadata_attributes=dict(name="email2"), require_db=True)
class LegacyEmailField(MutableScalarField[str, str]):
    """Field for legacy email addresses (``email1`` and ``email2``).

    This is a string field that also validates [#validation]_ any input to be
    email-like. It should only be used on string columns with names ``email1`` and
    ``email2``.

    .. [#validation] Validation is currently pretty basic, because validating emails is hard. The
      Sugar backend will have the final call on what is treated as valid.
    """

    @staticmethod
    def load_value(raw_value: JsonType) -> str:
        if not isinstance(raw_value, str):
            raise TypeError(
                f"string field must be populated with a string - got "
                f"{type(raw_value)!r}"
            )

        # Email parsing is hard, and we don't really know how Sugar does it. To make it
        # easy, everything with an at is considered somewhat valid:
        if "@" not in raw_value:
            raise ValueError(f"invalid email: {raw_value}")

        return raw_value

    @staticmethod
    def serialize(value: str) -> str:
        return LegacyEmailField.load_value(value)


@field_for_metadata.register(metadata_attributes=dict(type="varchar"), require_db=True)
@field_for_metadata.register(metadata_attributes=dict(type="text"), require_db=True)
@field_for_metadata.register(metadata_attributes=dict(type="encrypt"), require_db=True)
@field_for_metadata.register(metadata_attributes=dict(type="longtext"), require_db=True)
@field_for_metadata.register(metadata_attributes=dict(type="textarea"), require_db=True)
class StringField(MutableScalarField[str, str]):
    """Mutable field that handles the various string columns.

    This will handle any backend field that has the database type ``varchar``, ``text``,
    ``text``, ``encrypt``, ``longtext`` or ``textarea``.
    """

    @staticmethod
    def load_value(raw_value: JsonType) -> str:
        if not isinstance(raw_value, str):
            raise TypeError(
                f"string field must be populated with a string - got "
                f"{type(raw_value)!r}"
            )
        return raw_value

    @staticmethod
    def serialize(value: str) -> str:
        return value

    def starts_with(self, prefix: str) -> filtering.StringFilter:
        """Filter for values that start with a given string."""
        return filtering.StringStartsFilter(self.name, prefix)

    def ends_with(self, suffix: str) -> filtering.StringFilter:
        """Filter for values that end with a given string."""
        return filtering.StringEndsFilter(self.name, suffix)

    def contains(self, infix: str) -> filtering.StringFilter:
        """Filter for values that contain a given string."""
        return filtering.StringContainsFilter(self.name, infix)

    def not_empty(self) -> filtering.NotEmptyFilter:
        """Filter for non-empty values."""
        return filtering.NotEmptyFilter(self.name)


@field_for_metadata.register(metadata_attributes=dict(type="bool"), require_db=True)
class BooleanField(MutableScalarField[bool, bool]):
    """Mutable field for boolean columns."""

    @staticmethod
    def load_value(raw_value: JsonType) -> bool:
        if not isinstance(raw_value, bool):
            raise TypeError(
                f"boolean field must be populated with a boolean - got "
                f"{type(raw_value)!r}"
            )
        return raw_value

    @staticmethod
    def serialize(value: bool) -> bool:
        return value

    def true(self) -> filtering.ValuesFilter[bool]:
        """Filter for true values."""
        return self.values(True)

    def false(self) -> filtering.ValuesFilter[bool]:
        """Filter for false values."""
        return self.values(False)


@field_for_metadata.register(metadata_attributes=dict(type="float"), require_db=True)
@field_for_metadata.register(metadata_attributes=dict(type="decimal"), require_db=True)
class FloatField(MutableNumericField[float]):
    """Mutable field for floating-point number columns.

    This is appropriate for backend fields that have the type ``float`` or ``decimal``.
    """

    @staticmethod
    def load_value(raw_value: JsonType) -> float:
        if not isinstance(raw_value, float):
            raise TypeError(
                f"float field must be populated with a float - got "
                f"{type(raw_value)!r}"
            )
        return raw_value

    @staticmethod
    def serialize(value: float) -> float:
        return value


@field_for_metadata.register(metadata_attributes=dict(type="int"), require_db=True)
@field_for_metadata.register(metadata_attributes=dict(type="integer"), require_db=True)
@field_for_metadata.register(metadata_attributes=dict(type="long"), require_db=True)
@field_for_metadata.register(metadata_attributes=dict(type="smallint"), require_db=True)
@field_for_metadata.register(metadata_attributes=dict(type="tinyint"), require_db=True)
@field_for_metadata.register(metadata_attributes=dict(type="ulong"), require_db=True)
class IntegerField(MutableNumericField[int]):
    """Mutable field for integer columns.

    Use this for backend fields of type ``int``, ``integer``, ``long``, ``smallint``,
    ``tinyint`` or ``ulong``.
    """

    @staticmethod
    def load_value(raw_value: JsonType) -> int:
        if not isinstance(raw_value, int):
            raise TypeError(
                f"integer field must be populated with an int - got "
                f"{type(raw_value)!r}"
            )
        return raw_value

    @staticmethod
    def serialize(value: int) -> int:
        return value


EnumType = TypeVar("EnumType", bound="enum.Enum")


class EnumField(Generic[EnumType], MutableScalarField[EnumType, Union[str, int, bool]]):
    """Mutable field that represents *Dropdown* Sugar fields.

    :param enum: Pass an :class:`enum.Enum` type that represents the options for this
        field. This enum must have a non-null member named ``DEFAULT``. Further,
        elements should be strings (unless otherwise specified on the server side).
    """

    def __init__(
        self, enum: Type[EnumType], /, api_name: Optional[str] = None, **kwargs: Any
    ):
        try:
            assert enum["DEFAULT"] is not None
            has_default = True
        except (AssertionError, KeyError):
            has_default = False
        if not has_default:
            raise ValueError(
                "Cannot initialize an EnumField with an enum that does not have a "
                "default value. Make sure the enumeration contains a member named "
                "DEFAULT that is not None."
            )

        self._enum = enum
        super().__init__(api_name, **kwargs)

    def load_value(self, raw_value: JsonType) -> EnumType:
        if not isinstance(raw_value, (str, int, bool)):
            raise TypeError(
                f"integer field must be populated with an integer, string or boolean - "
                f"got {type(raw_value)!r}"
            )
        try:
            return self._enum(raw_value)
        except ValueError:
            return self._enum["DEFAULT"]

    def serialize(self, value: Union[EnumType, str, int]) -> Union[str, int, bool]:
        if isinstance(value, (str, int)):
            return value
        else:
            return cast(Union[str, int, bool], value.value)
