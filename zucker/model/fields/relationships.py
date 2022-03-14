from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any, Generic, Type, Union, overload

from ...exceptions import WrongClientError, WrongParadigmError
from ..view import AsyncModuleType, AsyncView, SyncModuleType, SyncView
from .base import Field, GetType, ModuleType

if TYPE_CHECKING:
    from ..module import AsyncModule, SyncModule

__all__ = ["RelatedField"]


class BaseRelatedField(
    Generic[ModuleType, GetType], Field[ModuleType, GetType], abc.ABC
):
    def __init__(
        self,
        link_name: str,
    ):
        if not isinstance(link_name, str):
            raise TypeError("related link names must be strings")
        link_name = link_name.strip()
        if len(link_name) == 0:
            raise ValueError("related link names must be non-empty")
        self._link_name = link_name

        super().__init__()


class SyncRelatedField(
    Generic[SyncModuleType], BaseRelatedField["SyncModule", SyncView[SyncModuleType]]
):
    def __init__(
        self,
        related_module: Type[SyncModuleType],
        link_name: str,
    ):
        from ..module import SyncModule

        if not issubclass(related_module, SyncModule):
            raise WrongParadigmError(
                f"cannot build a SyncRelatedField from non-synchronous type: "
                f"{related_module}"
            )
        self._related_module = related_module

        super().__init__(link_name)

    def _get_value(self, record: SyncModule) -> SyncView[SyncModuleType]:
        from ..module import SyncModule

        if not isinstance(record, SyncModule):
            raise WrongParadigmError(
                f"Cannot instantiate a synchronous record of type "
                f"{self._related_module!r} from a related field on the non-synchronous "
                f"module {type(record)!r}. If this module has multiple variations on "
                f"different clients, consider refactoring common parts into an "
                f"UnboundModule subclass and re-implementing related fields with the "
                f"correct targets in each subclass."
            )

        if record.get_client() is not self._related_module.get_client():
            raise WrongClientError()

        key = record.get_data("id")
        if key is None:
            raise ValueError("unable to retrieve key for related lookup")

        return SyncView(
            self._related_module,
            f"{record._api_name}/{key}/link/{self._link_name}",
        )


class AsyncRelatedField(
    Generic[AsyncModuleType],
    BaseRelatedField["AsyncModule", AsyncView[AsyncModuleType]],
):
    def __init__(
        self,
        related_module: Type[AsyncModuleType],
        link_name: str,
    ):
        from ..module import AsyncModule

        if not issubclass(related_module, AsyncModule):
            raise WrongParadigmError(
                f"cannot build an AsyncRelatedField from non-asynchronous type: "
                f"{related_module}"
            )
        self._related_module = related_module

        super().__init__(link_name)

    def _get_value(self, record: AsyncModule) -> AsyncView[AsyncModuleType]:
        from ..module import AsyncModule

        if not isinstance(record, AsyncModule):
            raise WrongParadigmError(
                f"Cannot instantiate an asynchronous record of type "
                f"{self._related_module!r} from a related field on the "
                f"non-asynchronous module {type(record)!r}. If this module has "
                f"multiple variations on different clients, consider refactoring "
                f"common parts into an UnboundModule subclass and re-implementing "
                f"related fields with the correct targets in each subclass."
            )

        if record.get_client() is not self._related_module.get_client():
            raise WrongClientError()

        key = record.get_data("id")
        if key is None:
            raise ValueError("unable to retrieve key for related lookup")

        return AsyncView(
            self._related_module,
            f"{record._api_name}/{key}/link/{self._link_name}",
        )


@overload
def RelatedField(
    related_module: Type[SyncModuleType], link_name: str
) -> SyncRelatedField[SyncModuleType]:
    ...


@overload
def RelatedField(
    related_module: Type[AsyncModuleType], link_name: str
) -> AsyncRelatedField[AsyncModuleType]:
    ...


def RelatedField(
    related_module: Union[Type[SyncModule], Type[AsyncModule]], link_name: str
) -> Union[SyncRelatedField[Any], AsyncRelatedField[Any]]:
    """Field that returns a view on a relationship link.

    :param related_module: The module type on the other side of the relationship.
    :param link_name: Name of the link.

    .. note::
      The related module used to initialize this field must be a bound module with the
      same client as the module the field is attached to. You can't mix synchronous and
      asynchronous models here.
    """
    from ..module import AsyncModule, SyncModule

    if issubclass(related_module, SyncModule):
        return SyncRelatedField(related_module, link_name)
    elif issubclass(related_module, AsyncModule):
        return AsyncRelatedField(related_module, link_name)
    else:
        raise TypeError(
            f"Cannot construct a related field from type {related_module!r}. "
            f"It must be initialized with a bound module - either a SyncModule or "
            f"an AsyncModule subclass."
        )
