from __future__ import annotations

from typing import TYPE_CHECKING, Generic, Type, Union, cast, overload

from ...exceptions import WrongClientError, WrongParadigmError
from ..view import AsyncModuleType, AsyncView, SyncModuleType, SyncView
from .base import Field

if TYPE_CHECKING:
    from ..module import AsyncModule, SyncModule, UnboundModule

__all__ = ["RelatedField"]


class RelatedField(
    Generic[SyncModuleType, AsyncModuleType],
    Field[SyncView[SyncModuleType], AsyncView[AsyncModuleType]],
):
    def __init__(
        self,
        related_module: Union[Type[SyncModuleType], Type[AsyncModuleType]],
        link_name: str,
        **kwargs,
    ):
        from ..module import AsyncModule, BaseModule, SyncModule

        if not issubclass(related_module, (SyncModule, AsyncModule)):
            if issubclass(related_module, BaseModule):  # type: ignore
                raise TypeError(
                    f"related fields must be initialized with a bound module - got the "
                    f"unbound variant {related_module!r}"
                )
            else:
                raise TypeError("a related module must be provided")
        if not isinstance(link_name, str):
            raise TypeError("related link names must be strings")
        link_name = link_name.strip()
        if len(link_name) == 0:
            raise ValueError("related link names must be non-empty")

        super().__init__(**kwargs)
        self._related_module: Union[
            Type[SyncModuleType], Type[AsyncModuleType]
        ] = related_module
        self._link_name = link_name

    @overload
    def _get_value(self, record: SyncModule) -> SyncView[SyncModuleType]:
        ...

    @overload
    def _get_value(self, record: AsyncModule) -> AsyncView[AsyncModuleType]:
        ...

    @overload
    def _get_value(self, record: UnboundModule) -> SyncView[SyncModuleType]:
        ...

    def _get_value(
        self, record: Union[SyncModule, AsyncModule, UnboundModule]
    ) -> Union[SyncView[SyncModuleType], AsyncView[AsyncModuleType]]:
        from ..module import AsyncModule, BoundModule, SyncModule

        if not isinstance(record, BoundModule):
            raise TypeError("felated fields can only be accessed on bound modules")

        key = record.get_data("id")
        if key is None:
            raise ValueError("unable to retrieve key for related lookup")

        if record.get_client() is not self._related_module.get_client():
            raise WrongClientError(
                "Related field was accessed from a different client that the defined "
                "module. Make sure that both the module the field is defined in as "
                "as the referring module are bound to the same client."
            )

        if isinstance(record, SyncModule):
            if not issubclass(self._related_module, SyncModule):
                raise WrongParadigmError(
                    f"Cannot instantiate a non-synchronous record of type "
                    f"{self._related_module!r} from a related field on a synchronous "
                    f"module. If this module has multiple variations on different "
                    f"clients, consider refactoring common parts into a BaseModule "
                    f"subclass and re-implementing related fields with the correct "
                    f"targets in each subclass."
                )
            return SyncView(
                cast(Type[SyncModuleType], self._related_module),
                f"{record._api_name}/{key}/link/{self._link_name}",
            )
        elif isinstance(record, AsyncModule):
            if not issubclass(self._related_module, AsyncModule):
                raise WrongParadigmError(
                    f"Cannot instantiate a non-asynchronous record of type "
                    f"{self._related_module!r} from a related field on an asynchronous "
                    f"module. If this module has multiple variations on different "
                    f"clients, consider refactoring common parts into a BaseModule "
                    f"subclass and re-implementing related fields with the correct "
                    f"targets in each subclass."
                )
            return AsyncView(
                cast(Type[AsyncModuleType], self._related_module),
                f"{record._api_name}/{key}/link/{self._link_name}",
            )
        else:
            raise TypeError(
                f"expecting a synchronous or asynchronous record, got {type(record)!r}"
            )
