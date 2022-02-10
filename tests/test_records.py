from typing import Callable
from unittest.mock import MagicMock

import pytest

from zucker import RequestsClient, UnsavedRecordError, model
from zucker.client import SyncClient


@pytest.fixture
def client() -> SyncClient:
    return RequestsClient("localhost", "u", "p")


class BaseDemo(model.UnboundModule):
    foo = model.StringField()
    bar = model.StringField()


class BaseDeno(model.UnboundModule):
    pass


def test_bound_init(client: SyncClient) -> None:
    class Demo(model.SyncModule, BaseDemo, client=client):
        pass

    # Make sure that records can't be created with the wrong API type.
    with pytest.raises(ValueError) as error:
        Demo(_module="Something")
    assert "API type" in str(error.value)
    with pytest.raises(ValueError) as error:
        Demo(_module="")
    assert "API type" in str(error.value)

    # TODO Test that each field gets validated successfully.


def test_strings(client: SyncClient) -> None:
    class Demo(model.SyncModule, BaseDemo, client=client):
        pass

    for func in list[Callable[[object], str]]((repr, str)):
        record = BaseDemo(id="one", name="Gustave")
        assert "BaseDemo" in func(record)
        assert "one" in func(record)
        assert "Gustave" in func(record)
        record = BaseDemo(id="two")
        assert "BaseDemo" in func(record)
        assert "two" in func(record)

        record = Demo(id="one", name="Gustave")
        assert "Demo" in func(record)
        assert "one" in func(record)
        assert "Gustave" in func(record)
        record = Demo(id="two")
        assert "Demo" in func(record)
        assert "two" in func(record)


def test_equality() -> None:
    first = BaseDemo(id="one")
    assert first != "one"
    assert first != ("Demo", "one")
    first_again = BaseDemo(id="one")
    assert first is not first_again
    assert first == first_again
    second = BaseDemo(id="two")
    assert first != second
    third = BaseDeno(id="one")
    assert first != third
    assert second != third
    fourth = BaseDemo()
    assert first != fourth
    assert second != fourth
    assert third != fourth


def test_new_record_saving(monkeypatch: pytest.MonkeyPatch, client: SyncClient) -> None:
    """New records (without IDs) are saved as expected."""
    request_mock = MagicMock(return_value={"id": "abc", "foo": "hi", "bar": "hu"})
    monkeypatch.setattr(client, "request", request_mock)

    class Demo(model.SyncModule, BaseDemo, client=client):
        pass

    record = Demo(foo="hi", bar="hu")
    record.save()

    request_mock.assert_called_once_with(
        "post", "Demo", json={"foo": "hi", "bar": "hu"}
    )
    assert record._id == "abc"
    assert record.foo == "hi"
    assert record.bar == "hu"


def test_existing_record_saving(
    monkeypatch: pytest.MonkeyPatch, client: SyncClient
) -> None:
    """Existing records (that have an ID) are saved as expected."""
    request_mock = MagicMock(return_value={"id": "abc", "foo": "f00", "bar": "hu"})
    monkeypatch.setattr(client, "request", request_mock)

    class Demo(model.SyncModule, BaseDemo, client=client):
        pass

    record = Demo(_module="Demo", id="abc", foo="hi", bar="hu")
    record.foo = "f00"
    record.save()

    request_mock.assert_called_once_with(
        "put",
        "Demo/abc",
        json={"foo": "f00"},
    )
    assert record._id == "abc"
    assert record.foo == "f00"
    assert record.bar == "hu"


def test_deleting_unsaved(client: SyncClient) -> None:
    class Demo(model.SyncModule, BaseDemo, client=client):
        pass

    record = Demo(foo="hi", bar="hu")
    with pytest.raises(UnsavedRecordError):
        record.delete()


def test_deleting(monkeypatch: pytest.MonkeyPatch, client: SyncClient) -> None:
    # A few things are relevant for testing here:
    # - The delete call gets issued
    # - _updated_data is empty afterwards
    # - The id is gone
    # - Other data is still available (updated values need to be merged into the
    #   original set)
    request_mock = MagicMock(return_value={})
    monkeypatch.setattr(client, "request", request_mock)

    class Demo(model.SyncModule, BaseDemo, client=client):
        pass

    record = Demo(_module="Demo", id="abc", foo="hi", bar="hu")
    record.foo = "f00"
    assert record.foo == "f00"
    record.delete()

    request_mock.assert_called_once_with("delete", "Demo/abc")
    assert record.get_data("id") is None
    assert record.foo == "f00"
    assert record.bar == "hu"
    assert len(record._updated_data) == 0


def test_refreshing(monkeypatch: pytest.MonkeyPatch, client: SyncClient) -> None:
    request_mock = MagicMock(return_value={"id": "abc", "foo": "f00", "bar": "b00"})
    monkeypatch.setattr(client, "request", request_mock)

    class Demo(model.SyncModule, BaseDemo, client=client):
        pass

    record = Demo(_module="Demo", id="abc", foo="hi", bar="hu")
    record.foo = "f11"
    record.refresh()

    request_mock.assert_called_once_with("get", "Demo/abc")
    assert record._id == "abc"
    assert record.foo == "f00"
    assert record.bar == "b00"
    assert len(record._updated_data) == 0
