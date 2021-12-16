from typing import Sequence, Union

import colored

from zucker.client import SyncClient
from zucker.model import fields

from ..inspection import (
    InspectedField,
    InspectedModule,
    get_metadata,
    inspect_modules_with_fields,
)

TERM = colored.attr("reset")
TERM_MODULE_NAME = colored.fg("blue")
TERM_MODULE_TITLE = TERM_MODULE_NAME + colored.attr("bold")
TERM_FIELD_NAME = colored.fg("red")
TERM_ARGUMENT_NAME = colored.fg("light_gray")


def indent(lines: Union[str, Sequence[str]], steps: int = 1) -> str:
    all_lines: Sequence[str]
    if isinstance(lines, str):
        all_lines = lines.split("\n")
    elif isinstance(lines, Sequence):
        all_lines = "\n".join(lines).split("\n")
    else:
        raise TypeError
    indentation = "  " * steps
    return indentation + f"\n{indentation}".join(all_lines)


def format_field(field: InspectedField) -> str:
    formatted_arguments = []
    for name, value in field.arguments.items():
        # Skip the api_name argument if it matches the field name (because then it's
        # redundant).
        if name == "api_name" and value == field.name:
            continue

        formatted_value: str
        if isinstance(value, InspectedModule):
            formatted_value = f"{TERM_MODULE_NAME}{value.name}{TERM}"
        else:
            formatted_value = repr(value)
        formatted_arguments.append(
            f"{TERM_ARGUMENT_NAME}{name}={TERM}{formatted_value}"
        )

    return " ".join(
        [
            f"{TERM_FIELD_NAME}{field.name}{TERM}",
            f"({field.field_type.__name__})",
            *formatted_arguments,
        ]
    )


def format_module(module: InspectedModule) -> str:
    argument_lines = [
        f"{key} = {value!r}"
        for key, value in module.class_arguments.items()
        # Skip the api_name argument if it matches the module name (because then it's
        # redundant).
        if key != "api_name" or value != module.name
    ]
    field_lines = [
        format_field(field)
        for field in sorted(module.fields, key=lambda field: field.name)
    ]

    return (
        "\n".join(
            [f"{TERM_MODULE_NAME}{module.name}{TERM}"]
            + (
                [
                    indent("Arguments:", 1),
                    indent(argument_lines, 2),
                ]
                if len(argument_lines) > 0
                else []
            )
            + ([indent(field_lines, 1)] if len(field_lines) > 0 else [])
        )
        + "\n"
    )


def run_inspect(client: SyncClient, **kwargs) -> None:
    metadata = get_metadata(client)
    modules = inspect_modules_with_fields(metadata)

    for module in sorted(modules, key=lambda module: module.name):
        print(format_module(module))
