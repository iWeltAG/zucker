from typing import Iterable
from uuid import uuid4

import pytest

from zucker import model
from zucker.client import SyncClient
from zucker.filtering import Combinator, FilterSet


class FakeClient(SyncClient):
    def __init__(self):
        super().__init__("http://test", "u", "p")
        self.data_callbacks = []

    def request(self, method, url, *, params={}, **kwargs):
        for func in self.data_callbacks:
            data = func(method, url, params)
            if data is not None:
                return data
        raise RuntimeError(f"requesting non_mocked {method} API call {url!r}")

    def set_data(self, method, url, response):
        def callback(given_method, given_url, params):
            if (method, url) == (given_method, given_url):
                return response

        self.add_data_callback(callback)

    def add_data_callback(self, callback):
        self.data_callbacks.append(callback)


@pytest.fixture
def fake_client(monkeypatch) -> FakeClient:
    client = FakeClient()
    return client


def test_init(fake_client: FakeClient):
    class Demo(model.SyncModule, client=fake_client):
        pass

    for not_applicable in (28, False):
        with pytest.raises(TypeError) as error:
            Demo.find(not_applicable)  # type: ignore
        assert "filter" in str(error.value)


def test_query_params_filters(fake_client: FakeClient):
    class Demo(model.SyncModule, client=fake_client):
        pass

    assert Demo.find(
        FilterSet(
            Combinator.OR,
            {
                "team_id": {
                    "$in": [
                        "45b33dd6-283d-8930-bcb8-5492a5289cec",
                        "e91b980c-e608-d6be-f117-54bfd22605e7",
                    ]
                }
            },
            {"status": {"$not_in": ["inprogess"]}},
        )
    )._filter_query_params == {
        "filter[0][$or][0][team_id][$in][0]": "45b33dd6-283d-8930-bcb8-5492a5289cec",
        "filter[0][$or][0][team_id][$in][1]": "e91b980c-e608-d6be-f117-54bfd22605e7",
        "filter[0][$or][1][status][$not_in][0]": "inprogess",
    }

    class FakeFilter:
        @staticmethod
        def build_filter() -> dict:
            return {
                "$and": [
                    {"team_id": {"$in": ["45b33dd6", "e91b980c"]}},
                    {
                        "$or": [
                            {"color": "yellow"},
                            {"age": 4},
                        ]
                    },
                ]
            }

    assert Demo.find(FakeFilter())._filter_query_params == {
        "filter[0][$and][0][team_id][$in][0]": "45b33dd6",
        "filter[0][$and][0][team_id][$in][1]": "e91b980c",
        "filter[0][$and][1][$or][0][color]": "yellow",
        "filter[0][$and][1][$or][1][age]": 4,
    }


def test_len(fake_client: FakeClient):
    class Demo(model.SyncModule, client=fake_client):
        pass

    fake_client.set_data("get", "Demo/count", {"record_count": 43})
    assert len(Demo.find()) == 43


def test_getting_id(fake_client: FakeClient):
    class Demo(model.SyncModule, client=fake_client):
        pass

    view = Demo.find()
    key = str(uuid4())

    def callback(given_method, given_url, params):
        if ("get", "Demo") == (given_method, given_url):
            assert params["max_num"] == 1
            assert params["fields"] == "id"
            assert params["filter[0][id][$equals]"] == key
            return {"records": [{"_module": "Demo", "id": key}]}

    fake_client.add_data_callback(callback)

    record = view[key]
    assert isinstance(record, Demo)
    assert record.get_data("id") == key

    for not_applicable in ("hello/world", "this has space"):
        with pytest.raises(ValueError) as error:
            record = view[not_applicable]
        assert "slash" in str(error.value) or "space" in str(error.value)


def test_getting_index(fake_client: FakeClient):
    class Demo(model.SyncModule, client=fake_client):
        pass

    def handle(method, url, params):
        if (method, url) == ("get", "Demo"):
            assert params["max_num"] == 1
            assert isinstance(params["offset"], int) and params["offset"] >= 0
            if params["offset"] > 10:
                return {"records": []}
            elif params["offset"] == 8:
                return {"records": [{"_module": "Demo", "id": "eight"}]}

    fake_client.add_data_callback(handle)
    view = Demo.find()

    record = view[8]
    assert isinstance(record, Demo)
    assert record.get_data("id") == "eight"

    with pytest.raises(IndexError):
        record = view[11]


def test_iterating_and_slices(fake_client: FakeClient):
    class Demo(model.SyncModule, client=fake_client):
        pass

    record_data = [
        {"_module": "Demo", "id": record_id}
        for record_id in (
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
        )
    ]

    def handle(method, url, params):
        if (method, url) == ("get", "Demo"):
            assert isinstance(params["max_num"], int) and params["max_num"] >= 0
            assert isinstance(params["offset"], int) and params["offset"] >= 0
            return {
                "records": record_data[
                    params["offset"] : params["offset"] + params["max_num"]
                ]
            }
        elif (method, url) == ("get", "Demo/count"):
            return {"record_count": len(record_data)}

    fake_client.add_data_callback(handle)
    view = Demo.find()
    view._chunk_size = 4

    def check_records(records: Iterable[Demo], definitions: Iterable[dict]):
        records = list(records)
        definitions = list(definitions)
        assert len(records) == len(definitions)
        for record, definition in zip(records, definitions):
            assert isinstance(record, Demo)
            assert record.get_data("id") == definition["id"]

    check_records(view[0:5], record_data[0:5])
    check_records(view[4:7], record_data[4:7])
    check_records(view[9:14], record_data[9:14])
    check_records(view[2:5:1], record_data[2:5:1])
    check_records(view[5:2], record_data[5:2])  # This is empty
    check_records(view[2:5:-1], record_data[2:5:-1])  # This too
    check_records(view[7:1:-1], record_data[7:1:-1])
    check_records(view[::-1], record_data[::-1])

    check_records(view, record_data)
    check_records(reversed(view), reversed(record_data))
