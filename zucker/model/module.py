from __future__ import annotations

import abc
from collections.abc import MutableMapping
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    ClassVar,
    Generic,
    Iterator,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)
from weakref import WeakValueDictionary

from zucker.exceptions import UnsavedRecordError

from ..client import AsyncClient, SyncClient
from ..filtering import GenericFilter
from ..utils import JsonMapping, JsonType, MutableJsonMapping
from .fields.base import Field
from .fields.scalars import IdField
from .view import AsyncView, SyncView, View

if TYPE_CHECKING:
    from ..client import BaseClient  # noqa: F401

ClientType = TypeVar("ClientType", bound="BaseClient", covariant=True)
NativeType = TypeVar("NativeType")
BoundSelf = TypeVar("BoundSelf", bound="BoundModule[BaseClient]")
SyncSelf = TypeVar("SyncSelf", bound="SyncModule")
AsyncSelf = TypeVar("AsyncSelf", bound="AsyncModule")

SyncOrAsync = Union[None, Awaitable[None]]


class BaseModule:
    """Base class for all modules.

    This class can be used to create unbounded base module types that can be reused as
    supertypes for actual models. To create actually usable module types, use the
    ``Module`` property of a client as the superclass.

    Module classes define the data model and are referred to as *records* when
    instantiated.
    """

    id = IdField()

    def __init__(self, **data: JsonType):
        self._original_data: JsonMapping = {}
        self._updated_data: MutableJsonMapping = {}
        self._set_data(data)

    #############################
    # Record instance - general #
    #############################

    def _repr_data(self) -> Sequence[str]:
        try:
            name = self["name"]
            assert isinstance(name, str)
            name_repr = f"- {name}"
        except KeyError:
            name_repr = ""
        id_repr = self.get_data("id", "")
        assert isinstance(id_repr, str)
        return (id_repr, name_repr)

    def __repr__(self) -> str:
        repr_data = (self.__class__.__name__, "record", *self._repr_data())
        return f"<{' '.join(repr_data)}>"

    def __eq__(self, other: Any) -> bool:
        """Test if this record reference is equal to another.

        Records are treated equal if their module and id match. When comparing two
        records that could potentially be in different modules, always compare the
        Record objects directly and not just their id properties.
        """
        if isinstance(other, type(self)):
            try:
                if self._id != other._id:
                    return False
            except KeyError:
                pass
            else:
                return True
        return False

    #####################################
    # Record instance - data management #
    #####################################

    def __getitem__(self, item: str) -> JsonType:
        if not isinstance(item, str):
            raise TypeError("module keys must be strings")

        try:
            value = self._updated_data[item]
            return value
        except (KeyError, TypeError):
            try:
                value = self._original_data[item]
                return value
            except (KeyError, TypeError):
                pass

        # This 'raise' statement is moved below (even though logically, it would fit
        # inside the inner 'except' in order to keep stack traces clean.
        raise KeyError(item)

    def _set_data(self, data: JsonMapping) -> None:
        self._original_data = {
            key: value for key, value in data.items() if not key.startswith("_")
        }
        self._updated_data = {}

    def get_data(
        self,
        key: str,
        default: Optional[NativeType] = None,
    ) -> Union[None, NativeType, JsonType]:
        """Get the current value of a specific key.

        This value may either come from the existing data populated when initializing
        the record or from any fields that have been updated / changed in the meantime.

        :param key: The key to look up.
        :param default: Default value to return when no value is found. If this is given
            and a value is found that doesn't match the default's type the default value
            is also returned.
        """
        try:
            value = self[key]
            if default is not None and not isinstance(value, type(default)):
                return default
            return value
        except KeyError:
            return default

    @property
    def _id(self) -> str:
        value = self["id"]
        if not isinstance(value, str):
            raise TypeError(f"got record ID of invalid type {type(value)!r}")
        return value

    ######################
    # Module information #
    ######################

    @classmethod
    def field_names(cls) -> Iterator[str]:
        """Iterate over all requested field names."""
        for key in dir(cls):
            if key.startswith("_"):
                continue
            if isinstance(getattr(cls, key, None), Field):
                yield key


class UnboundModule(BaseModule):
    """Unbound modules can be used as a base class for defining models that aren't
    connected to a client yet.
    """


class BoundModule(Generic[ClientType], BaseModule, abc.ABC):
    """Bound modules are module classes are already scoped to a client and therefore
    also to the sync or async paradigm.

    Bound modules contain all the logic that enables server-side communication. That
    means that bound records (records are the instances of module classes) can be
    saved, refreshed and deleted.
    """

    _CLIENT_TYPE: ClassVar[Type[ClientType]]
    _client: ClassVar[ClientType]
    _api_name: ClassVar[str]

    # Cache object that allows direct access to records by their ID. References here are
    # held weakly - that means that once the corresponding view is garbage collected,
    # entries in this cache may no longer be accessible.
    _record_cache: ClassVar[MutableMapping[str, BoundModule[ClientType]]]

    def __init_subclass__(
        cls,
        client: Optional[ClientType] = None,
        api_name: Optional[str] = None,
        **kwargs,
    ):
        if not abc.ABC in cls.__bases__:
            if not isinstance(client, cls._CLIENT_TYPE):
                raise TypeError(
                    f"expecting client of type {cls._CLIENT_TYPE!r}, got "
                    f"{type(client)!r}"
                )
            cls._client = client
            cls._api_name = api_name or cls.__name__
            cls._record_cache = WeakValueDictionary()

    @classmethod
    def get_client(cls) -> ClientType:
        """Client instance bounded to this module.

        This client will be used for all server-side communication. Further, any caches
        are scoped to this client.
        """
        return cls._client

    @property
    def client(self) -> ClientType:
        """Shorthand for :meth:`get_client`."""
        return self.get_client()

    #############################
    # Record instance - general #
    #############################

    def _repr_data(self) -> Sequence[str]:
        return (f"(via {self._api_name})", *super()._repr_data())

    def __eq__(self, other: Any) -> bool:
        """Test if this record reference is equal to another.

        Records are treated equal if their module and id match. When comparing two
        records that could potentially be in different modules, always compare the
        Record objects directly and not just their id properties.
        """
        if isinstance(other, type(self)):
            if self._api_name != other._api_name:  # pragma: no cover
                # This case shouldn't ever happen (and if it does it would be undefined
                # behaviour). Since we already checked that the other model has a
                # different type the only way this can happen is when a user
                # intentionally sets the _api_name on a record instance.
                return False
            if self.client is not other.client:
                return False
        return super().__eq__(other)

    def _set_data(self, data: JsonMapping) -> None:
        if data.get("_module", self._api_name) != self._api_name:
            raise ValueError(
                f"trying to set {self.__class__.__name__} record data the wrong API "
                f"type - got {data['_module']}, expecting {self._api_name}"
            )
        super()._set_data(data)

    #######################################
    # Record instance - server operations #
    #######################################

    @property
    def _mutation_endpoint(self) -> str:
        if self.get_data("id") is None:
            raise UnsavedRecordError("cannot mutate a non-saved record")
        return f"{self._api_name}/{self._id}"

    def _prepare_save(self) -> Tuple[str, str, JsonMapping]:
        """Prepare everything for a save step that doesn't require the client yet.

        This method returns a tuple containing an HTTP method, an endpoint and a
        JSON mapping that should be passed as payload. Once the save method has called
        the corresponding client, the resulting data from the request should be passed
        to :meth:``_finalize_save``.
        """
        # Get the record id (or None). This is used to determine whether we are updating
        # an existing record or creating a new one.
        record_id = self.get_data("id")

        if record_id is None:
            data_keys = set(self._updated_data.keys()) | set(self._original_data.keys())
        else:
            # If the record is already present on the server, we only need to send the
            # updated data points.
            data_keys = set(self._updated_data.keys())

        for key in data_keys:
            if key.startswith("_"):
                raise ValueError(f"cannot save underscore-prefixed key {key!r}")
        data = {key: self[key] for key in data_keys}

        if record_id is None:
            return "post", self._api_name, data
        else:
            if "id" in data:
                # TODO This should no longer be required (and could be converted into an
                #  assert) when the IdField is actually used.
                raise ValueError("cannot change a record's ID")
            return "put", f"{self._api_name}/{record_id}", data

    def _finalize_save(self, record_data: JsonMapping) -> None:
        self._set_data(record_data)

    @abc.abstractmethod
    def save(self) -> SyncOrAsync:
        """Save all updated fields back to the server."""

    def _finalize_delete(self) -> None:
        # Merge any updated data into the original data set (because we no longer have
        # a server-side record to match).
        data_keys = set(self._updated_data.keys()) | set(self._original_data.keys())
        self._original_data = {key: self.get_data(key) for key in data_keys}
        if "id" in self._original_data:
            del self._original_data["id"]
        self._updated_data = {}

    def _finalize_refresh(self, record_data: JsonMapping) -> None:
        self._set_data(record_data)

    @abc.abstractmethod
    def delete(self) -> SyncOrAsync:
        """Delete this record.

        Calling this method will delete the record on the server and remove the ID
        information from this module record instance. Subsequent calls to :meth:`save`
        will create a new record.
        """

    @abc.abstractmethod
    def refresh(self, *, _record_data: Optional[JsonMapping] = None) -> SyncOrAsync:
        """Refresh cached data from the server.

        This will clear any updated data that has been manually saved and not set yet.
        """

    ##########################
    # Record / view building #
    ##########################

    @classmethod
    @abc.abstractmethod
    def find(
        cls: Type[BoundSelf],
        *filters: Union[JsonMapping, GenericFilter]
        # This huge generic basically amounts to: "Any view that returns either Selfs
        # and optional Selfs or the same thing, but awaitable":
    ) -> View[
        BoundSelf,
        Union[BoundSelf, Awaitable[BoundSelf]],
        Union[Optional[BoundSelf], Awaitable[Optional[BoundSelf]]],
    ]:
        """Create a view on the module.

        Any parameters passed here will be used as filters.
        """

    # @classmethod
    # def get(
    #     cls: Type[Self], *filters: Union[JsonMapping, GenericFilter]
    # ) -> Optional[Self]:
    #     """Return the first and only element in a view, if it is present."""
    #     view = cls.find(*filters)
    #     if len(view) != 1:
    #         return None
    #     else:
    #         return view[0]

    @classmethod
    def _lookup_record_cache(cls: Type[BoundSelf], key: str) -> Optional[BoundSelf]:
        item = cls._record_cache.get(key, None)
        if item is None:
            return None
        assert isinstance(item, cls)
        return item

    def _cache_self(self) -> None:
        self._record_cache[self._id] = self

    @classmethod
    @abc.abstractmethod
    def get_by_id(
        cls: Type[BoundSelf], key: str
    ) -> Union[Optional[BoundSelf], Awaitable[Optional[BoundSelf]]]:
        """Retrieve a record object by the ID."""


class SyncModule(BoundModule[SyncClient], abc.ABC):
    _CLIENT_TYPE = SyncClient

    @classmethod
    def find(
        cls: Type[SyncSelf], *filters: Union[JsonMapping, GenericFilter]
    ) -> SyncView[SyncSelf]:
        view = SyncView(cls, cls._api_name)
        if len(filters) > 0:
            view = view.filtered(*filters)
        return view

    def save(self) -> None:
        method, endpoint, data = self._prepare_save()
        record_data = self.client.request(method, endpoint, json=data)
        self._finalize_save(record_data)

    def delete(self) -> None:
        self.client.request("delete", self._mutation_endpoint)
        self._finalize_delete()

    def refresh(self, *, _record_data: Optional[JsonMapping] = None) -> None:
        record_data = self.client.request("get", self._mutation_endpoint)
        self._finalize_refresh(record_data)

    @classmethod
    def get_by_id(cls: Type[SyncSelf], key: str) -> Optional[SyncSelf]:
        return cls.find().get_by_id(key)


class AsyncModule(BoundModule[AsyncClient], abc.ABC):
    _CLIENT_TYPE = AsyncClient

    @classmethod
    def find(
        cls: Type[AsyncSelf], *filters: Union[JsonMapping, GenericFilter]
    ) -> AsyncView[AsyncSelf]:
        view = AsyncView(cls, cls._api_name)
        if len(filters) > 0:
            view = view.filtered(*filters)
        return view

    async def save(self) -> None:
        method, endpoint, data = self._prepare_save()
        record_data = await self.client.request(method, endpoint, json=data)
        self._finalize_save(record_data)

    async def delete(self) -> None:
        await self.client.request("delete", self._mutation_endpoint)
        self._finalize_delete()

    async def refresh(self, *, _record_data: Optional[JsonMapping] = None) -> None:
        record_data = await self.client.request("get", self._mutation_endpoint)
        self._finalize_refresh(record_data)

    @classmethod
    async def get_by_id(cls: Type[AsyncSelf], key: str) -> Optional[AsyncSelf]:
        return await cls.find().get_by_id(key)
