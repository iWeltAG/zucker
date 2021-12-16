from typing import Any, Mapping, MutableMapping, Sequence, TypeVar, Union, cast

__all__ = [
    "JsonPrimitive",
    "JsonType",
    "JsonMapping",
    "MutableJsonMapping",
    "ApiType",
    "check_json_primitive",
    "check_json_mapping",
    "check_json",
]


# MyPy currently doesn't support recursive types, so we can't actually build a correct
# 'JSON' type yet. See here: https://github.com/python/mypy/issues/731
#
# JsonType = Union[None, bool, str, int, float, Mapping[str, "JsonType"], Sequence["JsonType"]]
JsonPrimitive = Union[None, bool, str, int, float]
JsonType = Union[JsonPrimitive, Mapping, Sequence]

JsonMapping = Mapping[str, JsonType]
MutableJsonMapping = MutableMapping[str, JsonType]

ApiType = TypeVar("ApiType", bound=JsonType)


def check_json_primitive(data: Any) -> JsonPrimitive:
    """Check if the provided object is a valid JSON primitive and return it."""
    if not isinstance(data, (type(None), bool, str, int, float)):
        raise TypeError(f"expected JSON primitive, got f{data}")
    return data


def check_json_mapping(data: Any) -> JsonMapping:
    """Recursively check if the provided object is a valid JSON mapping and
    return it.
    """
    if not isinstance(data, Mapping):
        raise TypeError(f"expected JSON dictionary, got f{data}")
    for key, value in data.items():
        if not isinstance(key, str):
            raise TypeError(f"expected string key, got {type(key)!r}")
        check_json(value)
    return cast(JsonMapping, data)


def check_json(data: Any) -> JsonType:
    """Recursively check if a provided data object is valid JSON (in the respective
    native Python types) and return it.

    This method is used as a type guard for input that comes from the backend.
    """
    try:
        return check_json_primitive(data)
    except TypeError:
        pass

    if isinstance(data, Sequence):
        for item in data:
            check_json(item)
        return cast(JsonType, data)
    elif isinstance(data, Mapping):
        return check_json_mapping(data)

    raise TypeError(f"expected valid JSON type, got {type(data)!r}")
