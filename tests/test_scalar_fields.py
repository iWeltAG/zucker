import uuid

import hypothesis
import pytest
from hypothesis import strategies as st

from zucker.model import IdField


@hypothesis.given(st.integers(0, 2**128))
def test_id_field_loading(value: int) -> None:
    hex_value = hex(value)[2:].zfill(32)
    formatted_uuid = f"{hex_value[:8]}-{hex_value[8:12]}-{hex_value[12:16]}-{hex_value[16:20]}-{hex_value[20:]}"

    field = IdField()
    uuid_from_field = field.load_value(formatted_uuid)
    assert uuid_from_field == uuid.UUID(int=value)
    assert field.serialize(uuid_from_field) == formatted_uuid


def test_id_field_errors() -> None:
    field = IdField()
    with pytest.raises(ValueError):
        field.load_value("01234567-89ab-zzzz-0123-56789abcdef0")
    with pytest.raises(ValueError):
        field.serialize("01234567-89ab-zzzz-0123-56789abcdef0")
    with pytest.raises(TypeError):
        field.load_value(1234)
    with pytest.raises(TypeError):
        field.load_value({})
    with pytest.raises(TypeError):
        field.load_value(None)
