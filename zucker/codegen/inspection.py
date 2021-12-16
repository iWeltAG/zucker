from __future__ import annotations

from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Mapping,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
)

from zucker.client import SyncClient
from zucker.exceptions import InvalidSugarResponseError
from zucker.utils import JsonMapping, JsonPrimitive

if TYPE_CHECKING:
    from zucker.model.fields.base import Field

    FieldInitializerReturnType = Optional[
        tuple[Type[Field[Any, Any]], Mapping[str, Any]]
    ]
    JsonPrimitiveOrCheckFn = Union[
        JsonPrimitive, Type[Any], Callable[[JsonPrimitive], bool]
    ]

_F = TypeVar("_F", bound="Field[Any, Any]", covariant=True)

__all__ = [
    "InspectedModule",
    "InspectedField",
    "field_for_metadata",
    "get_metadata",
    "inspect_modules_with_fields",
]


@dataclass
class InspectedModule:
    name: str
    fields: Sequence[InspectedField]
    class_arguments: Mapping[str, Any]
    raw_metadata: JsonMapping


@dataclass
class InspectedField:
    name: str
    field_type: Type[Field[Any, Any]]
    arguments: Mapping[str, Any]
    raw_metadata: JsonMapping


@dataclass
class FieldInspectionContext:
    field_metadata: JsonMapping
    modules: Mapping[str, InspectedModule]


class FieldMetadataRegistry:
    def __init__(self) -> None:
        self.field_initializers: list[
            Callable[[FieldInspectionContext], FieldInitializerReturnType]
        ] = []
        self.field_types: set[Type[Field[Any, Any]]] = set()

    def __call__(self, context: FieldInspectionContext) -> FieldInitializerReturnType:
        results = (initialize(context) for initialize in self.field_initializers)
        valid_results = [result for result in results if result is not None]
        if len(valid_results) == 0:
            return None
        elif len(valid_results) > 1:
            raise RuntimeError("more than one field matched for metadata block")
        else:
            return valid_results[0]

    def register(
        self,
        metadata_attributes: Optional[Mapping[str, JsonPrimitiveOrCheckFn]] = None,
        optional_metadata_attributes: Optional[
            Mapping[str, JsonPrimitiveOrCheckFn]
        ] = None,
        require_db: bool = False,
        output_arguments: Union[
            None,
            Mapping[str, Any],
            Callable[[FieldInspectionContext], Mapping[str, Any]],
        ] = None,
    ) -> Callable[[Type[_F]], Type[_F]]:
        """Register a server-side metadata construct that this field supports.

        The attribute options passed here are the ones you get when querying server
        metadata and looking in the 'fields' value in a module. The
        `Sugar Documentation`_ has a more detailed explanation of what information this
        object contains. These are passed in two parameters:

        - ``metadata_attributes`` contains attributes that the field must have in order
          to match. This is a dictionary where each value is either the direct attribute
          value or a callback that returns a boolean.
        - ``optional_metadata_attributes`` works the same way, but will also accept a
          field when the attribute isn't present at all (but will still reject when the
          value does not match).

        If the ``require_db`` parameter is true, the field will only match if the ``source``
        attribute is not ``non-db``.

        When inspection is run, any field that has attributes matching those given
        here will be exported as the field type that is decorated with this method.
        These attribute may either be given directly or
        The ``output_arguments`` option can be used to suggest field arguments for the
        newly created field.

        .. _Sugar Documentation: https://support.sugarcrm.com/Documentation/Sugar_Developer/Sugar_Developer_Guide_10.0/Data_Framework/Vardefs/#Fields_Array
        """

        def decorate(field_type: Type[_F]) -> Type[_F]:
            def initialize(
                context: FieldInspectionContext,
            ) -> FieldInitializerReturnType:
                def check_metadata_attribute(
                    key: str, expected_value: JsonPrimitiveOrCheckFn
                ) -> Optional[bool]:
                    # Go through the entire metadata tree and find the exact subtree we
                    # are looking for. This will make sure that when we are given a key
                    # of 'full_text_search.enabled' we are actually looking at the
                    # full_text_search subtree.
                    path_names = key.split(".")
                    current_item = context.field_metadata
                    for path_name in path_names:
                        if not isinstance(current_item, Mapping):
                            return None
                        if path_name not in current_item:
                            return None
                        current_item = current_item[path_name]  # type: ignore

                    # current_item should now be the expected value. The latter may
                    # either be given directly, as a type or as a callable.
                    if isinstance(expected_value, type):
                        if not isinstance(current_item, expected_value):
                            return False
                    elif callable(expected_value):
                        try:
                            if not expected_value(current_item):  # type: ignore
                                return False
                        except:
                            return False
                    else:
                        if current_item != expected_value:
                            return False
                    return True

                for item in (metadata_attributes or {}).items():
                    if check_metadata_attribute(*item) is not True:
                        return None
                for item in (optional_metadata_attributes or {}).items():
                    # Optional attributes must either match or not be present.
                    if check_metadata_attribute(*item) is False:
                        return None
                if require_db and (
                    check_metadata_attribute(
                        "source", lambda source: source != "non-db"
                    )
                    is False
                ):
                    return None

                # If we got until here, the field matches.
                suggested_arguments: Mapping[str, Any]
                if output_arguments is None:
                    suggested_arguments = {}
                elif callable(output_arguments):
                    try:
                        suggested_arguments = output_arguments(context)
                    except:
                        return None
                else:
                    suggested_arguments = output_arguments

                extra_arguments = {}
                if "name" in context.field_metadata:
                    extra_arguments["api_name"] = context.field_metadata["name"]

                return field_type, {**extra_arguments, **suggested_arguments}

            self.field_initializers.append(initialize)
            self.field_types.add(field_type)
            return field_type

        return decorate


field_for_metadata = FieldMetadataRegistry()


def get_metadata(client: SyncClient) -> JsonMapping:
    client.fetch_metadata("modules")
    return client.get_metadata_item("modules")


def inspect_modules_with_fields(metadata: Any) -> Sequence[InspectedModule]:
    # TODO Convert these to actual type guards:

    def assert_sugar_mapping(mapping: Any) -> None:
        if not isinstance(mapping, Mapping):
            raise InvalidSugarResponseError(
                f"expecting mapping type, got {type(mapping)!r}"
            )

    def assert_sugar_contains(mapping: Any, name: str) -> None:
        assert_sugar_mapping(mapping)
        if name not in mapping:
            raise InvalidSugarResponseError(f"expecting mapping that contains {name!r}")

    assert_sugar_contains(metadata, "modules")

    # First pass: create an inspection result for each module. This allows all modules
    # to be referenced, even if their fields haven't been populated yet.
    modules: dict[str, InspectedModule] = {}
    for module_name, module_metadata in metadata["modules"].items():
        if module_name in modules:
            raise InvalidSugarResponseError(
                f"got duplicate module name: {module_name!r}"
            )
        modules[module_name] = InspectedModule(
            name=module_name,
            fields=[],
            class_arguments=dict(
                api_name=module_name,
            ),
            raw_metadata=module_metadata,
        )

    # Second pass: go through each module again and inspect their fields.
    for module_name, module_metadata in metadata["modules"].items():
        assert_sugar_contains(module_metadata, "fields")
        assert_sugar_mapping(module_metadata["fields"])

        fields = list[InspectedField]()

        for field_name, field_metadata in module_metadata["fields"].items():
            if "name" in field_metadata and field_name != field_metadata["name"]:
                raise InvalidSugarResponseError(
                    f"non-matching field names {field_name!r} (from field set key) and "
                    f"{field_metadata['name']!r} (from actual field metadata)"
                )

            inspect_context = FieldInspectionContext(
                field_metadata=field_metadata,
                modules=modules,
            )
            inspect_result = field_for_metadata(inspect_context)
            if inspect_result is None:
                continue

            inspected_field = InspectedField(
                name=field_name,
                field_type=inspect_result[0],
                arguments=inspect_result[1],
                raw_metadata=field_metadata,
            )
            fields.append(inspected_field)

        modules[module_name].fields = fields

    return list(modules.values())
