from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from zucker import model
from zucker.codegen.inspection import (
    FieldInspectionContext,
    InspectedField,
    InspectedModule,
    field_for_metadata,
    inspect_modules_with_fields,
)
from zucker.codegen.interactive.inspect import indent
from zucker.utils import MutableJsonMapping


@st.composite
def field_names(draw: st.DrawFn) -> str:
    return draw(st.text(min_size=1))


def augment_field_data(
    *,
    draw: st.DrawFn,
    arguments: MutableJsonMapping,
    raw_metadata: MutableJsonMapping,
    name: str,
    **kwargs: None,
) -> None:
    """Add common arguments and metadata when generating inspected fields.

    This function doesn't really follow best practices, but it works for testing here.
    The idea is you call it with ``**locals()`` as the parameter and it will add the
    required properties.
    """
    arguments["api_name"] = name
    raw_metadata["name"] = name
    raw_metadata["help"] = draw(st.text())
    raw_metadata["comment"] = draw(st.text())
    raw_metadata["comments"] = draw(st.text())
    raw_metadata["audited"] = draw(st.booleans())


@st.composite
def inspected_boolean_fields(draw: st.DrawFn) -> InspectedField:
    name = draw(field_names())
    arguments: MutableJsonMapping = {}
    raw_metadata: MutableJsonMapping = {"type": "bool", "default": draw(st.booleans())}

    augment_field_data(**locals())

    return InspectedField(
        name=name,
        field_type=model.BooleanField,
        arguments=arguments,
        raw_metadata=raw_metadata,
    )


@st.composite
def inspected_string_fields(draw: st.DrawFn) -> InspectedField:
    name = draw(field_names())
    sugar_type = draw(st.sampled_from(("text", "varchar")))
    arguments: MutableJsonMapping = {}
    raw_metadata: MutableJsonMapping = dict(name=name, type=sugar_type)

    if sugar_type == "text":
        rows, cols = draw(st.tuples(st.integers(1, 8), st.integers(20, 100)))
        raw_metadata.update(rows=rows, cols=cols)
    elif sugar_type == "varchar":
        length = draw(st.integers(20, 300))
        raw_metadata["length"] = length

    augment_field_data(**locals())

    return InspectedField(
        name=name,
        field_type=model.StringField,
        arguments=arguments,
        raw_metadata=raw_metadata,
    )


@st.composite
def inspected_scalar_fields(draw: st.DrawFn) -> InspectedField:
    return draw(st.one_of(inspected_boolean_fields(), inspected_string_fields()))


@st.composite
def inspected_modules(draw: st.DrawFn) -> InspectedModule:
    name = draw(field_names())

    def get_field_name(inspected_field: InspectedField) -> str:
        return inspected_field.name

    fields = draw(st.lists(inspected_scalar_fields(), unique_by=get_field_name))
    class_arguments = {"api_name": name}
    raw_metadata = {"fields": {field.name: field.raw_metadata for field in fields}}

    return InspectedModule(
        name=name,
        fields=fields,
        class_arguments=class_arguments,
        raw_metadata=raw_metadata,
    )


@given(st.lists(st.text()))
def test_indenting(lines: list[str]) -> None:
    all_lines = "\n".join(lines).split("\n")
    for steps in range(0, 10):
        expected_result = "\n".join("  " * steps + line for line in all_lines)
        assert indent(lines, steps) == expected_result
        assert indent("\n".join(lines), steps) == expected_result


@given(inspected_scalar_fields())
def test_field_resolving(inspected_field: InspectedField) -> None:
    context = FieldInspectionContext(
        # Here, the metadata object from the generated inspection result is used to see
        # if an actual inspection yields the same result.
        field_metadata=inspected_field.raw_metadata,
        modules={},
    )
    result = field_for_metadata(context)
    assert result is not None
    field_type, arguments = result
    assert field_type is inspected_field.field_type


@given(inspected_modules())
def test_module_inspection(module: InspectedModule) -> None:
    metadata = {"modules": {module.name: module.raw_metadata}}

    inspection_result = inspect_modules_with_fields(metadata)
    assert len(inspection_result) == 1
    inspected_module = inspection_result[0]
    assert inspected_module == module
