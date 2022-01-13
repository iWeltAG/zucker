from typing import Any, Literal, Optional, Union

import pytest

from zucker.filtering import BasicFilter, Combinator, FilterSet
from zucker.filtering.combining import FilterOrMapping
from zucker.model.fields.base import ScalarField
from zucker.utils import JsonMapping, JsonType, MutableJsonMapping


def fs_and(*given_parts: Union[FilterOrMapping, None]) -> FilterSet:
    return FilterSet(Combinator.AND, *given_parts)


def fs_or(*given_parts: Union[FilterOrMapping, None]) -> FilterSet:
    return FilterSet(Combinator.OR, *given_parts)


def test_filterset_init() -> None:
    with pytest.raises(TypeError):
        fs_and(1)  # type: ignore
    with pytest.raises(TypeError):
        fs_and(False, {})  # type: ignore


def test_filterset_building() -> None:
    class DummyFilter:
        @staticmethod
        def build_filter() -> JsonMapping:
            return {"is": "okay"}

    assert fs_or(DummyFilter(), {"hello": "world"}).build_filter() == {
        "$or": [{"is": "okay"}, {"hello": "world"}]
    }
    assert fs_and({"hello": "world"}, DummyFilter()).build_filter() == {
        "$and": [{"hello": "world"}, {"is": "okay"}]
    }


def test_filterset_expanding() -> None:
    assert fs_and({"a": 1}, fs_or({"b": 2})).build_filter() == {
        "$and": [{"a": 1}, {"b": 2}]
    }
    assert fs_and({"a": 1}, fs_or({"b": 2}, {"c": 3})).build_filter() == {
        "$and": [{"a": 1}, {"$or": [{"b": 2}, {"c": 3}]}]
    }
    assert fs_and({"a": 1}, fs_and({"b": 2}, {"c": 3})).build_filter() == {
        "$and": [{"a": 1}, {"b": 2}, {"c": 3}]
    }

    class DummyFilter:
        @staticmethod
        def build_filter() -> JsonMapping:
            return {"b": 2}

    assert fs_or({"a": 1}, DummyFilter()).build_filter() == {
        "$or": [{"a": 1}, {"b": 2}]
    }


def test_filterset_combining() -> None:
    assert (fs_and({"a": 1}) & {"b": 1}).build_filter() == {
        "$and": [{"a": 1}, {"b": 1}]
    }
    assert (fs_and({"a": 1}) | {"b": 1}).build_filter() == {"$or": [{"a": 1}, {"b": 1}]}
    assert (fs_and({"a": 1}, {"b": 2}) | fs_and({"c": 3}, {"d": 4})).build_filter() == {
        "$or": [{"$and": [{"a": 1}, {"b": 2}]}, {"$and": [{"c": 3}, {"d": 4}]}]
    }

    class DummyFilter:
        @staticmethod
        def build_filter() -> JsonMapping:
            return {"a": 1}

    assert ({"a": 1} | fs_or({"b": 2})).build_filter() == {"$or": [{"a": 1}, {"b": 2}]}
    assert (DummyFilter() & fs_and({"b": 2})).build_filter() == {
        "$and": [{"a": 1}, {"b": 2}]
    }


def test_filterset_immutability() -> None:
    first_source = {"a": 1}
    first = fs_and(first_source)
    assert first.build_filter() == {"$and": [{"a": 1}]}
    first_source["a"] = 2
    assert first.build_filter() == {"$and": [{"a": 1}]}

    class DummyFilter:
        x: MutableJsonMapping = {"c": 3}

        def build_filter(self) -> JsonMapping:
            return self.x

    second = fs_and({"b": 2}, DummyFilter())
    assert second.build_filter() == {"$and": [{"b": 2}, {"c": 3}]}
    DummyFilter.x["c"] = 4
    assert second.build_filter() == {"$and": [{"b": 2}, {"c": 3}]}


class DemoField(ScalarField[Any, Any]):
    def __init__(self, name: str, **kwargs: Any):
        super().__init__(**kwargs)
        self.__set_name__(None, name)  # type: ignore

    @classmethod
    def load_value(cls, raw_value: JsonType) -> Any:
        return raw_value

    @classmethod
    def serialize(cls, value: JsonType) -> Any:
        return value


def test_field_name_errors() -> None:
    for non_str in (2, [3], False):
        with pytest.raises(TypeError) as first_error:
            DemoField(non_str)  # type: ignore
        assert "field name" in str(first_error.value)
    for invalid_name in ("", "hello world", "   notgood   "):
        with pytest.raises(ValueError) as second_error:
            DemoField(invalid_name)
        assert "field name" in str(second_error.value)


def test_field_values_filter() -> None:
    with pytest.raises(TypeError):
        DemoField("x").values(False)
    with pytest.raises(TypeError):
        DemoField("x").values(1, [])
    with pytest.raises(ValueError):
        DemoField("x").values()

    result = {"name": {"$equals": "Ben"}}
    assert DemoField("name").values("Ben").build_filter() == result
    assert (DemoField("name") == "Ben").build_filter() == result

    assert DemoField("last_name").values("Paul", "Spencer").build_filter() == {
        "last_name": {"$in": ("Paul", "Spencer")}
    }

    result = {"name": {"$not_equals": "Mike"}}
    assert (~DemoField("name").values("Mike")).build_filter() == result
    assert (DemoField("name") != "Mike").build_filter() == result

    assert (
        ~DemoField("last_name").values("Emma", "Rachel", "Steven")
    ).build_filter() == {"last_name": {"$not_in": ("Emma", "Rachel", "Steven")}}


def test_field_null_filter() -> None:
    result = {"employer": {"$is_null": None}}
    assert DemoField("employer").null().build_filter() == result
    assert (DemoField("employer") == None).build_filter() == result

    result = {"employer": {"$not_null": None}}
    assert (~DemoField("employer").null()).build_filter() == result
    assert (DemoField("employer") != None).build_filter() == result


def test_field_combining() -> None:
    class DummyFilter(BasicFilter[int]):
        operator = "$"

    assert (DummyFilter("a", 1) | DummyFilter("b", 2)).build_filter() == {
        "$or": [{"a": {"$": 1}}, {"b": {"$": 2}}]
    }
    assert (DummyFilter("a", 1) & DummyFilter("b", 2)).build_filter() == {
        "$and": [{"a": {"$": 1}}, {"b": {"$": 2}}]
    }
    assert FilterSet(
        Combinator.AND, (DummyFilter("a", 1) | DummyFilter("b", 2))
    ).build_filter() == {"$or": [{"a": {"$": 1}}, {"b": {"$": 2}}]}
