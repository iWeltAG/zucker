from typing import (
    Any,
    Mapping,
    MutableMapping,
    Sequence,
    TypeGuard,
    TypeVar,
    Union,
    cast,
)

__all__ = [
    "JsonPrimitive",
    "JsonType",
    "JsonMapping",
    "MutableJsonMapping",
    "ApiType",
    "is_json_primitive",
    "is_json_mapping",
    "is_json",
]


# MyPy currently doesn't support recursive types, so we can't actually build a correct
# 'JSON' type yet. See here: https://github.com/python/mypy/issues/731
#
JsonPrimitive = Union[None, bool, str, int, float]
JsonType = Union[JsonPrimitive, Mapping[str, "JsonType"], Sequence["JsonType"]]
NonNoneJsonType = Union[
    bool, str, int, float, Mapping[str, "JsonType"], Sequence["JsonType"]
]

JsonMapping = Mapping[str, JsonType]
MutableJsonMapping = MutableMapping[str, JsonType]

ApiType = TypeVar("ApiType", bound=JsonType)


def is_json_primitive(value: Any) -> TypeGuard[JsonPrimitive]:
    """Check if the provided object is a valid JSON primitive."""
    return isinstance(value, (type(None), bool, str, int, float))


def is_json_mapping(value: Any) -> TypeGuard[JsonMapping]:
    """Recursively check if the provided object is a valid JSON mapping."""
    if not isinstance(value, Mapping):
        return False
    for key, value in value.items():
        if not isinstance(key, str):
            return False
        if not is_json(value):
            return False
    return True


def is_json(value: Any) -> TypeGuard[JsonType]:
    """Recursively check if a provided data object is valid JSON (in the respective
    native Python types).
    """
    if is_json_primitive(value) or is_json_mapping(value):
        return True
    elif isinstance(value, Sequence):
        for item in value:
            if not is_json(item):
                return False
        return True
    else:
        return False
