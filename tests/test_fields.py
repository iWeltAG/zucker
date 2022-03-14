import pytest
from hypothesis import given
from hypothesis import strategies as st

from zucker import RequestsClient
from zucker.client import SyncClient
from zucker.model import (
    BooleanField,
    RelatedField,
    StringField,
    SyncModule,
    UnboundModule,
)
from zucker.model.fields.base import AnyModule, MutableField
from zucker.model.view import SyncView


@pytest.fixture
def client() -> SyncClient:
    return RequestsClient("localhost", "u", "p")


class DemoField(MutableField[AnyModule, str, str]):
    def _get_value(self, record: AnyModule) -> str:
        return "strawberry"

    def _set_value(self, record: AnyModule, value: str) -> None:
        if value != "raspberry":
            raise ValueError("must set 'raspberry'")


class BaseDemo(UnboundModule):
    something = DemoField()
    other_thing = DemoField(api_name="something")


def test_field_name() -> None:
    with pytest.raises(RuntimeError):
        DemoField().name
    with pytest.raises(TypeError):
        DemoField(api_name=False)  # type: ignore
    with pytest.raises(ValueError):
        DemoField(api_name="this is not valid")
    with pytest.raises(ValueError):
        DemoField(api_name="")

    assert BaseDemo.something.name == "something"
    assert BaseDemo.other_thing.name == "something"


def test_getting_and_setting(client: SyncClient) -> None:
    record = BaseDemo()
    assert record.something == "strawberry"

    with pytest.raises(ValueError):
        record.something = "nothing"
    record.something = "raspberry"


@given(st.text())
def test_string_field_values(raw_value: str) -> None:
    assert StringField.serialize(StringField.load_value(raw_value)) == raw_value


@given(st.booleans())
def test_boolean_field_values(raw_value: bool) -> None:
    assert BooleanField.serialize(BooleanField.load_value(raw_value)) == raw_value


def test_related_field_initialization(client: SyncClient) -> None:
    class Demo(SyncModule, BaseDemo, client=client):
        pass

    with pytest.raises(TypeError):
        # TODO Add a typing test here
        RelatedField(None, "link")  # type: ignore
    with pytest.raises(TypeError, match="must be initialized with a bound module"):
        # TODO same
        RelatedField(BaseDemo, "demo")  # type: ignore
    for link_name in ("", "   "):
        with pytest.raises(ValueError, match="related link names"):
            RelatedField(Demo, link_name)


def test_related_view_building(client: SyncClient) -> None:
    class Demo(SyncModule, BaseDemo, client=client):
        pass

    field = RelatedField(Demo, "some_link")
    with pytest.raises(ValueError):
        field._get_value(Demo())
    result = field._get_value(Demo(id="the_id"))
    assert isinstance(result, SyncView)
    assert result._module is Demo
    assert result._base_endpoint == "Demo/the_id/link/some_link"
