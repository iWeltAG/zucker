from typing import Any, Optional

import pytest

from zucker.filtering import BasicFilter, Combinator, FilterSet
from zucker.model.fields.base import ScalarField
from zucker.utils import JsonMapping, JsonType


def fs_and(*args) -> FilterSet:
    return FilterSet(Combinator.AND, *args)


def fs_or(*args) -> FilterSet:
    return FilterSet(Combinator.OR, *args)


def test_filterset_init():
    with pytest.raises(TypeError):
        fs_and(1)
    with pytest.raises(TypeError):
        fs_and(False, {})


def test_filterset_building():
    class DummyFilter:
        @staticmethod
        def build_filter() -> dict:
            return {"is": "okay"}

    assert fs_or(DummyFilter(), {"hello": "world"}).build_filter() == {
        "$or": [{"is": "okay"}, {"hello": "world"}]
    }
    assert fs_and({"hello": "world"}, DummyFilter()).build_filter() == {
        "$and": [{"hello": "world"}, {"is": "okay"}]
    }


def test_filterset_expanding():
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


def test_filterset_combining():
    assert (fs_and({"a": 1}) & {"b": 1}).build_filter() == {
        "$and": [{"a": 1}, {"b": 1}]
    }
    assert (fs_and({"a": 1}) | {"b": 1}).build_filter() == {"$or": [{"a": 1}, {"b": 1}]}
    assert (fs_and({"a": 1}, {"b": 2}) | fs_and({"c": 3}, {"d": 4})).build_filter() == {
        "$or": [{"$and": [{"a": 1}, {"b": 2}]}, {"$and": [{"c": 3}, {"d": 4}]}]
    }

    class DummyFilter:
        @staticmethod
        def build_filter() -> dict:
            return {"a": 1}

    assert ({"a": 1} | fs_or({"b": 2})).build_filter() == {"$or": [{"a": 1}, {"b": 2}]}
    assert (DummyFilter() & fs_and({"b": 2})).build_filter() == {
        "$and": [{"a": 1}, {"b": 2}]
    }


def test_filterset_immutability():
    first_source = {"a": 1}
    first = fs_and(first_source)
    assert first.build_filter() == {"$and": [{"a": 1}]}
    first_source["a"] = 2
    assert first.build_filter() == {"$and": [{"a": 1}]}

    class DummyFilter:
        x: JsonMapping = {"c": 3}

        def build_filter(self) -> JsonMapping:
            return self.x

    second = fs_and({"b": 2}, DummyFilter())
    assert second.build_filter() == {"$and": [{"b": 2}, {"c": 3}]}
    DummyFilter.x["c"] = 4
    assert second.build_filter() == {"$and": [{"b": 2}, {"c": 3}]}


class DemoField(ScalarField[Any, Any]):
    def __init__(self, name: str, **kwargs):
        super().__init__(**kwargs)
        self.__set_name__(None, name)  # type: ignore

    @classmethod
    def load_value(cls, raw_value: JsonType) -> Any:
        return raw_value

    @classmethod
    def serialize(cls, value: JsonType) -> Any:
        return value


def test_field_name_errors():
    for non_str in (2, [3], False):
        with pytest.raises(TypeError) as error:
            DemoField(non_str)  # type: ignore
        assert "field name" in str(error.value)
    for invalid_name in ("", "hello world", "   notgood   "):
        with pytest.raises(ValueError) as error:
            DemoField(invalid_name)
        assert "field name" in str(error.value)


def test_field_values_filter():
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


def test_field_null_filter():
    result = {"employer": {"$is_null": None}}
    assert DemoField("employer").null().build_filter() == result
    assert (DemoField("employer") == None).build_filter() == result

    result = {"employer": {"$not_null": None}}
    assert (~DemoField("employer").null()).build_filter() == result
    assert (DemoField("employer") != None).build_filter() == result


def test_field_combining():
    class DummyFilter(BasicFilter):
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
