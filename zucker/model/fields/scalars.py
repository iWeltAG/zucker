from __future__ import annotations

from datetime import datetime
from typing import Union
from uuid import UUID

from zucker import filtering
from zucker.codegen.inspection import field_for_metadata
from zucker.utils import JsonType

from .base import MutableScalarField, ScalarField

__all__ = ["StringField", "BooleanField", "IdField"]


@field_for_metadata.register(metadata_attributes=dict(type="varchar"), require_db=True)
@field_for_metadata.register(metadata_attributes=dict(type="text"), require_db=True)
class StringField(MutableScalarField[str, str]):
    @staticmethod
    def load_value(raw_value: JsonType) -> str:
        if not isinstance(raw_value, str):
            raise ValueError(
                f"string field must be populated with a str - got {type(raw_value)!r}"
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


@field_for_metadata.register(metadata_attributes=dict(type="bool"), require_db=True)
class BooleanField(MutableScalarField[bool, bool]):
    @staticmethod
    def load_value(raw_value: JsonType) -> bool:
        if not isinstance(raw_value, bool):
            raise ValueError(
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


class IdField(ScalarField[UUID, str]):
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
