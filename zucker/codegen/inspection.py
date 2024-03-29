from __future__ import annotations

from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    MutableSequence,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from zucker.client import SyncClient
from zucker.exceptions import InvalidSugarResponseError
from zucker.utils import JsonMapping, JsonPrimitive, JsonType, is_json_mapping

if TYPE_CHECKING:
    from zucker.model.fields.base import Field

    FieldInitializerReturnType = Optional[
        Tuple[Type[Field[Any, Any]], Mapping[str, Any]]
    ]
    JsonPrimitiveOrCheckFn = Union[
        JsonPrimitive, Type[Any], Callable[[JsonPrimitive], bool]
    ]

_F = TypeVar("_F", bound="Field[Any, Any]", covariant=True)

__all__ = [
    "InspectedModule",
    "InspectedField",
    "field_for_metadata",
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
    module_name: str
    field_name: str
    field_metadata: JsonMapping
    modules: Mapping[str, InspectedModule]
    client: SyncClient


class EnumRepr:
    def __init__(self, name: str, values: Sequence[str]):
        self._repr = f"enum.Enum({repr(name)}, {repr(values)})"

    def __repr__(self) -> str:
        return self._repr


def inspect_enum(context: FieldInspectionContext) -> Mapping[str, Any]:
    enum_data = context.client.request(
        "get", f"{context.module_name}/enum/{context.field_name}"
    )
    return {
        "enum": EnumRepr(
            f"{context.module_name}_{context.field_name}", list(enum_data.keys())
        )
    }


class FieldMetadataRegistry:
    def __init__(self) -> None:
        self.field_initializers: List[
            Callable[[FieldInspectionContext], FieldInitializerReturnType]
        ] = []
        self.field_types: Set[Type[Field[Any, Any]]] = set()

    def __call__(self, context: FieldInspectionContext) -> FieldInitializerReturnType:
        """Find the first registered field that accepts a specified context."""
        for initialize in self.field_initializers:
            result = initialize(context)
            if result is not None:
                return result
        return None

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
                    current_item: Union[JsonMapping, JsonType] = context.field_metadata
                    for path_name in path_names:
                        if not isinstance(current_item, Mapping):
                            return None
                        if path_name not in current_item:
                            return None
                        current_item = current_item[path_name]
                    value = cast(JsonType, current_item)

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


def inspect_modules_with_fields(
    modules_metadata: JsonMapping, client: SyncClient
) -> Sequence[InspectedModule]:
    # First pass: create an inspection result for each module. This allows all modules
    # to be referenced, even if their fields haven't been populated yet.
    modules: Dict[str, InspectedModule] = {}
    for module_name, module_metadata in modules_metadata.items():
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
            raw_metadata=module_metadata,  # type: ignore
        )

    # Second pass: go through each module again and inspect their fields.
    for module_name, module_metadata in modules_metadata.items():
        if (
            not isinstance(module_metadata, Mapping)
            or "fields" not in module_metadata
            or not isinstance(module_metadata["fields"], Mapping)
        ):
            raise InvalidSugarResponseError("expected JSON mapping for module metadata")

        fields: MutableSequence[InspectedField] = []

        for field_name, field_metadata in module_metadata["fields"].items():
            if not isinstance(field_metadata, Mapping):
                raise InvalidSugarResponseError(
                    "expected JSON mapping for field metadata"
                )
            if "name" in field_metadata and field_name != field_metadata["name"]:
                raise InvalidSugarResponseError(
                    f"non-matching field names {field_name!r} (from field set key) and "
                    f"{field_metadata['name']!r} (from actual field metadata)"
                )

            inspect_context = FieldInspectionContext(
                module_name=module_name,
                field_name=field_name,
                field_metadata=field_metadata,
                modules=modules,
                client=client,
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
