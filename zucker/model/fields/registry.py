import typing
from typing import Any, Callable, MutableMapping, Type

from .base import Field


class FieldRegistry:
    def __init__(self):
        self._field_types: MutableMapping[Type[Any], Type[Field]] = {}

    def __call__(self, native_type: Type[Any], **kwargs) -> Field:
        """Create a field instance for a given Python vanilla type."""
        if not isinstance(native_type, type):
            raise TypeError("create_field_for_type takes a type as the first argument")

        field_type = self._field_types.get(native_type, None)
        if field_type is None:
            raise NotImplementedError(
                f"Cannot create a field for the unknown type {native_type!r}. If the "
                f"type is custom, make sure to register a field with the "
                f"field_for_type dispatcher."
            )

        return field_type(**kwargs)

    def register_for_type(
        self,
        native_type: Type[Any],
    ) -> Callable[[Type[Field]], Type[Field]]:
        if not isinstance(native_type, type):
            raise TypeError(
                f"registering field types takes a native type as an argument, "
                f"got {native_type!r}"
            )

        def decorate(field_type: Type[Field]) -> Type[Field]:
            if not isinstance(field_type, type) or not issubclass(field_type, Field):
                raise TypeError(
                    f"registering field types must be used as decorator on a subclass "
                    f"of Field, got {field_type!r}"
                )
            self._field_types[native_type] = field_type
            return field_type

        return decorate

    def register(self, field_type: Type[Field]) -> Type[Field]:
        # The __orig_bases__ attribute here is the only place in this method where we
        # need to use typing implementation details in order to inspect the generic
        # arguments. This property is a tuple which contains the original (typed)
        # base classes of the field, before they were evaluated. Each of these (or at
        # least the relevant Field[..., ...] one) is an instance of _GenericAlias.
        # See here for another related example: https://stackoverflow.com/a/60984681
        # The parameter __orig_bases__ itself was found here:
        # https://github.com/ilevkivskyi/typing_inspect/blob/01f1b91391658e541bd156b8577eb2feaccc7670/typing_inspect.py#L573
        field_bases = list(
            base
            for base in getattr(field_type, "__orig_bases__", ())
            # Find only those bases that extend from Field (namely ScalarField), of
            # which there should be exactly one.
            if (lambda base: isinstance(base, type) and issubclass(base, Field))(
                typing.get_origin(base)
            )
        )
        if not len(field_bases) == 1:
            raise TypeError(
                f"to register a field, it must extend from the Field type and "
                f"correctly provide generic arguments, got {field_type!r}"
            )

        # For the further processing below, we can now rely on actually supported
        # methods from the typing module which let us extract the generic arguments
        # passed to that alias, as described in the StackOverflow answer linked above.
        try:
            native_type, _ = typing.get_args(field_bases[0])
        except ValueError as error:
            raise ValueError(
                f"could not extract native type from generic field definition: {error}"
            )

        return self.register_for_type(native_type)(field_type)


field_for_type = FieldRegistry()
