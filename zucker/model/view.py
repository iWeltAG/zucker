from __future__ import annotations

import abc
import sys
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from functools import cached_property
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Dict,
    Generic,
    Iterable,
    Iterator,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)
from uuid import UUID

from ..exceptions import InvalidSugarResponseError
from ..filtering import Combinator, FilterSet, GenericFilter
from ..utils import JsonMapping, JsonType, check_json_mapping

if TYPE_CHECKING:
    from ..client import BaseClient  # noqa: F401
    from .module import AsyncModule, BoundModule, SyncModule  # noqa: F401

ModuleType = TypeVar("ModuleType", bound="BoundModule[BaseClient]")
SyncModuleType = TypeVar("SyncModuleType", bound="SyncModule")
AsyncModuleType = TypeVar("AsyncModuleType", bound="AsyncModule")
GetReturn = TypeVar("GetReturn", covariant=True)
OptionalGetReturn = TypeVar("OptionalGetReturn", covariant=True)
Self = TypeVar("Self", bound="View[Any, Any, Any]")


class View(Generic[ModuleType, GetReturn, OptionalGetReturn], abc.ABC):
    """Generic view class.

    The first generic argument should be passed when initializing a view and point to
    the module's type. The other two are only used internally and set by
    :class:`SyncView` and :class:`AsyncView`. They determine the type of results that
    are returned from the abstract methods.
    """

    def __init__(self, module: Type[ModuleType], base_endpoint: str = ""):
        """Build a new view.

        :param module: A class that inherits from :class:`Module` which is used to
            construct record objects. This class also determines which fields will be
            retrieved (anything that isn't defined in the module class will be ignored
            even if the server provides it).
        :param base_endpoint: Base endpoint to start queries from (without the server
            URL, which the client provides). For a simple module query, this is the
            module's name. When querying for related records, it will be something like
            ``<module>/<id>/link/<link name>``.
        """
        self._module = module
        self._base_endpoint = base_endpoint
        self._filter: Optional[GenericFilter] = None

        # The range is the current subset of indexes in the dataset that this view
        # points to. When a sub-view is created by using the slice square brackets
        # notation, the slice is added to a list of pending slices, which are all
        # applied to the range when required. That way, we can defer evaluation as long
        # as possible and are also paradigm-agnostic.
        self._range: Optional[range] = None
        self._pending_slices = list[slice]()

        # This parameter holds the total size of the view - not just that part that is
        # targeted by the range. This is fetched by calling .prefetch_size()
        self._size: Optional[int] = None

        # The record cache for this view is different from the one in the module itself
        # in that this one
        # a) holds strong references so that it is ensured that the cache is actually
        #    useful for the entire lifetime of the view.
        # b) maps from offsets instead of IDs to the corresponding record objects. That
        #    means we can iterate over the view multiple times without needing to
        #    re-fetch data.
        # This cache is meant to be supplementary to the other one - this one is for
        # iterating, the other is for accessing objects by ID.
        self._record_cache: Dict[int, Optional[ModuleType]] = {}

    #################
    # Magic methods #
    #################

    def __repr__(self) -> str:
        module_name = self._module.__name__
        prefix = "filtered view" if self._filter else "view"

        if self._range is None:
            range_repr = ""
        else:
            range_repr_parts = ["", "", ""]
            if self._range.step < 0:
                if self._range.start != sys.maxsize - 1:
                    range_repr_parts[0] = str(self._range.start)
                if self._range.stop != -1:
                    range_repr_parts[1] = str(self._range.stop)
            else:
                if self._range.start != 0:
                    range_repr_parts[0] = str(self._range.start)
                if self._range.stop != sys.maxsize:
                    range_repr_parts[1] = str(self._range.stop)
            if self._range.step != 1:
                range_repr_parts[2] = str(self._range.step)
            # Make sure we don't get an overhang like "1::"
            if range_repr_parts[2] == "":
                range_repr_parts.pop()
            range_repr = (
                ""
                if all(part == "" for part in range_repr_parts)
                else f"[{':'.join(range_repr_parts)}]"
            )

        return f"<{prefix} on {module_name}{range_repr}>"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, View):
            return False
        if other._module is not self._module:
            return False
        return all(
            getattr(self, attr) == getattr(other, attr)
            for attr in ("_base_endpoint", "_filter")
        )

    @overload
    def __getitem__(self, item: Union[UUID, str]) -> GetReturn:
        ...

    @overload
    def __getitem__(self, item: int) -> GetReturn:
        ...

    @overload
    def __getitem__(self: Self, item: slice) -> Self:
        ...

    def __getitem__(
        self: Self, item: Union[UUID, str, int, slice]
    ) -> Union[GetReturn, Self]:
        # First case - retrieving a single record by it's ID, which may either be given
        # as a string or as a UUID object.
        if isinstance(item, (UUID, str)):
            item = str(item)
            record = self.get_by_id(item)

            # Ignore this type for now until MyPy supports generic self types. See the
            # comment in __get__ in the base Field class for details.
            return record  # type: ignore

        # Second case - retrieving a single record by it's offset in the view.
        elif isinstance(item, int):
            record = self.get_by_index(item)

            # Same typing stuff as above.
            return record  # type: ignore

        # Third case - taking a slice of the view. This will return a new subview, which
        # is evaluated lazily and won't fetch any data until asked.
        elif isinstance(item, slice):
            if any(
                not isinstance(value, (type(None), int))
                for value in (item.start, item.stop, item.step)
            ):
                raise TypeError("module views only support slicing by integers")

            with self._clone() as view:
                view._pending_slices.append(item)

            return view

        else:
            raise TypeError(
                f"items in a module view must be referenced either by ID, offset or "
                f"slice; got {type(item)!r}"
            )

    ##########################
    # Extending and chaining #
    ##########################

    def filtered(self: Self, *filters: Union[JsonMapping, GenericFilter]) -> Self:
        """Return a clone of this view which contains additional filters.

        :param filters: Additional filters for the new view. These should be provided as
            filter-type objects (for example those generated by fields). Alternatively,
            naive dictionaries (those `available`_ from Sugar) are also supported. When
            multiple filters are provided, they will be AND-ed together.

        .. _available: https://support.sugarcrm.com/Documentation/Sugar_Developer/Sugar_Developer_Guide_9.0/Integration/Web_Services/REST_API/Endpoints/module_GET/#Filter_Expressions
        """
        with self._clone() as view:
            if len(filters) == 1 and isinstance(filters[0], GenericFilter):
                view._filter = filters[0]
            else:
                view._filter = FilterSet(Combinator.AND, self._filter, *filters)
        return view

    def reversed(self: Self) -> Self:
        """Return a clone of this view, but with reversed iteration order.

        This is identical to ``view[::-1]``.
        """
        return self[::-1]

    @contextmanager
    def _clone(self: Self) -> Iterator[Self]:
        """Make a new view that builds on this one, while trying to preserve the cache
        as much as possible.

        This is intended to be used as a context manager:

        .. code-block:: python

            with self._clone() as view:
                view._filter = ...
            return view

        After closing the context manager, the view will be finalized. This step tries
        to copy as much of the record cache as possible.
        """
        view = self.__class__(self._module, self._base_endpoint)
        view._filter = self._filter
        view._range = self._range
        view._pending_slices = self._pending_slices[:]

        try:
            yield view
        finally:
            # When the filter changes, we need a clean cache anyway because server-side
            # offsets may be different now.
            if view._filter != self._filter:
                return

            # In the other case, the cache can be shared between the new and old views.
            # Remember, the cache stores the server-side offsets so there shouldn't be
            # a problem with two views writing to the same cache object.
            view._record_cache = self._record_cache
            view._size = self._size

    ###################
    # Record fetching #
    ###################

    def _prepare_get_by_id(self: Self, key: str) -> Self:
        if "/" in key or " " in key:
            raise ValueError("record keys cannot contain slashes or spaces")

        return self.filtered(self._module.id == key)

    @abc.abstractmethod
    def get_by_id(self, key: str) -> OptionalGetReturn:
        """Retrieve a record object by it's ID."""

    def _prepare_get_by_offset(
        self, offset: int
    ) -> Union[ModuleType, Tuple[str, str, JsonMapping]]:
        if (cache_entry := self._record_cache.get(offset, None)) is not None:
            return cache_entry

        return (
            "get",
            # https://support.sugarcrm.com/Documentation/Sugar_Developer/Sugar_Developer_Guide_11.1/Integration/Web_Services/REST_API/Endpoints/module_GET/
            f"{self._base_endpoint}",
            dict(
                max_num=1,
                offset=offset,
                **self._query_params,
            ),
        )

    def _finalize_get_by_offset(
        self, offset: int, data: JsonMapping
    ) -> Optional[ModuleType]:
        if "records" not in data or not isinstance(data["records"], Sequence):
            raise InvalidSugarResponseError(
                "records filter request did not return any data"
            )
        if len(data["records"]) > 1:
            raise InvalidSugarResponseError(
                f"requested a single record but got more that one response"
            )

        if len(data["records"]) == 0:
            record = None
        else:
            record_data = data["records"][0]
            try:
                record = self._module(**check_json_mapping(record_data))
            except TypeError:
                raise InvalidSugarResponseError("got invalid record data")
        self._record_cache[offset] = record
        return record

    @abc.abstractmethod
    def _get_by_offset(self, offset: int) -> OptionalGetReturn:
        """Retrieve a record object by the server-side offset, which depends on the
        current filtering.
        """

    @abc.abstractmethod
    def get_by_index(self, index: int) -> OptionalGetReturn:
        """Retrieve a record object by it's index in this view."""

    def _index_to_offset(self, index: int) -> Optional[int]:
        """Convert an offset into a server-side index.

        The difference between the two enumeration numerals is the following: indexes
        describe the actual 0-based numbering used when using *this* view as a sequence.
        It is used both when accessing it using the ``view[3]` syntax (to get the third
        record) or when iterating, for example using a ``for`` loop or something like
        ``list(view)``. These offsets differ from view to view and their ordering is
        dependent on a number of things, like:

        - The current query (filters)
        - Range the view is targeting

        Offsets on the other hand refer to the ones that the server will accept. Though
        this isn't strictly global either, it doesn't depend on the view's range any
        more. The only thing that can change offsets is when the filter gets changed.

        To sum up:

            >>> SomeModule.find()[3] # Index 3, Offset 3
            ... SomeModule.find()[3:][3] # Index 3, Offset 6
            ... SomeModule.find(some_filter)[3] # Index 3, Index depending on the filter
        """
        if index < 0:
            return None
        try:
            assert isinstance(self._range, range), "view range has not been calculated"
            return self._range[index]
        except IndexError:
            return None

    def _offset_to_index(self, offset: int) -> Optional[int]:
        try:
            assert isinstance(self._range, range), "view range has not been calculated"
            return self._range.index(offset)
        except ValueError:
            return None

    @cached_property
    def _query_params(self) -> JsonMapping:
        return {
            "fields": ",".join(self._module.field_names()),
            **self._filter_query_params,
        }

    @property
    def _filter_query_params(self) -> JsonMapping:
        """Render out the current filter into query parameters.

        This method will convert a filter that renders out to something like this:

        >>> {
        ...     "a": 1,
        ...     "b": [ 2, 3 ],
        ...     "c": { "d": 4 },
        ... }

        Into a dictionary like this:

        >>> {
        ...     "a": 1,
        ...     "b[0]": 2,
        ...     "b[1]": 3,
        ...     "c[d]": 4,
        ... }

        The result can be passed to an HTTP library to use as query parameters.
        """
        if self._filter is None:
            return {}

        params = {}

        def parse_filter(prefix: str, filter_definition: JsonType) -> None:
            """Recursively parse a filter definition and add the appropriate parameters
            to the result object."""
            if isinstance(filter_definition, (str, int, float, bool)):
                params["filter{}".format(prefix)] = filter_definition
                return

            iterator: Iterable[tuple[str, JsonType]]
            if isinstance(filter_definition, Mapping):
                iterator = filter_definition.items()
            elif isinstance(filter_definition, Sequence):
                iterator = enumerate(filter_definition)  # type: ignore
            else:
                raise TypeError(
                    f"invalid filter definition type: {type(filter_definition)}"
                )

            for key, value in iterator:
                parse_filter(f"{prefix}[{key}]", value)

        parse_filter("", [self._filter.build_filter()])

        return params


class SyncView(
    Generic[SyncModuleType],
    View[SyncModuleType, SyncModuleType, Optional[SyncModuleType]],
):
    #################
    # Magic methods #
    #################

    def __len__(self) -> int:
        self._calculate_range()
        assert isinstance(self._range, range)
        return len(self._range)

    def __iter__(self) -> Iterator[SyncModuleType]:
        self._calculate_range()
        assert isinstance(self._range, range)
        iterator = iter(self._range)
        current_offset, next_offset = next(iterator, None), next(iterator, None)

        while current_offset is not None:
            # TODO Things this approach is currently missing:
            #  - Batching. At the moment, this will send a request to the server for
            #    each requested record. The batching implementation should also respect
            #    reversed ranges (when using reversed() or something like [::-1] on the
            #    view).
            #  - Dynamically determining view size, which would nullify the need for
            #    calling '/count' beforehand (which happens in __len__() in
            #    _validate_range()). This is probably only feasible for forward
            #    iteration though.
            record = self._get_by_offset(current_offset)
            if record is not None:
                yield record

            current_offset, next_offset = next_offset, next(iterator, None)

    def __reversed__(self) -> Iterator[SyncModuleType]:
        return iter(self[::-1])

    ###################
    # Record fetching #
    ###################

    def _fetch_size(self) -> None:
        """Fetch the total number of results that can be queried from this view's
        filters."""
        data = self._module.get_client().request(
            "get",
            # https://support.sugarcrm.com/Documentation/Sugar_Developer/Sugar_Developer_Guide_11.1/Integration/Web_Services/REST_API/Endpoints/modulecount_GET/
            f"{self._base_endpoint}/count",
            params=self._query_params,
        )
        record_count = data.get("record_count", None)
        if not isinstance(record_count, int):
            raise InvalidSugarResponseError(
                f"got invalid record count: {record_count!r}"
            )
        self._size = record_count

    def _calculate_range(self) -> None:
        """Apply all pending slicing operations on the cached range object."""
        if self._range is None:
            if self._size is None:
                self._fetch_size()
            assert isinstance(self._size, int)
            self._range = range(0, self._size, 1)
        while len(self._pending_slices) > 0:
            self._range = self._range[self._pending_slices.pop(0)]

    def get_by_id(self, key: str) -> Optional[SyncModuleType]:
        try:
            return self._prepare_get_by_id(key)[0]
        except IndexError:
            pass
        raise KeyError(key)

    def _get_by_offset(self, offset: int) -> Optional[SyncModuleType]:
        preparation = self._prepare_get_by_offset(offset)
        if isinstance(preparation, tuple):
            method, endpoint, params = preparation
            data = self._module.get_client().request(method, endpoint, params=params)
            return self._finalize_get_by_offset(offset, data)
        else:
            return preparation

    def get_by_index(self, index: int) -> Optional[SyncModuleType]:
        self._calculate_range()

        offset = self._index_to_offset(index)
        if offset is None:
            raise IndexError(index)
        record = self._get_by_offset(offset)
        if record is None:
            raise IndexError(index)
        return record


class AsyncView(
    Generic[AsyncModuleType],
    View[
        AsyncModuleType,
        Awaitable[AsyncModuleType],
        Awaitable[Optional[AsyncModuleType]],
    ],
):
    async def length(self) -> int:
        await self._calculate_range()
        assert isinstance(self._range, range)
        return len(self._range)

    # The following two methods are exactly the same as the the corresponding SyncView
    # implementations, with the exception of them awaiting asynchronous methods.

    async def _fetch_size(self) -> None:
        """Fetch the total number of results that can be queried from this view's
        filters."""
        data = await self._module.get_client().request(
            "get",
            # https://support.sugarcrm.com/Documentation/Sugar_Developer/Sugar_Developer_Guide_11.1/Integration/Web_Services/REST_API/Endpoints/modulecount_GET/
            f"{self._base_endpoint}/count",
            params=self._query_params,
        )
        record_count = data.get("record_count", None)
        if not isinstance(record_count, int):
            raise InvalidSugarResponseError(
                f"got invalid record count: {record_count!r}"
            )
        self._size = record_count

    async def _calculate_range(self) -> None:
        """Apply all pending slicing operations on the cached range object."""
        if self._range is None:
            if self._size is None:
                await self._fetch_size()
            assert isinstance(self._size, int)
            self._range = range(0, self._size, 1)
        while len(self._pending_slices) > 0:
            self._range = self._range[self._pending_slices.pop(0)]

    ###################
    # Record fetching #
    ###################

    async def get_by_id(self, key: str) -> Optional[AsyncModuleType]:
        try:
            return await self._prepare_get_by_id(key)[0]
        except IndexError:
            pass
        raise KeyError(key)

    async def _get_by_offset(self, offset: int) -> Optional[AsyncModuleType]:
        preparation = self._prepare_get_by_offset(offset)
        if isinstance(preparation, tuple):
            method, endpoint, params = preparation
            data = await self._module.get_client().request(
                method, endpoint, params=params
            )
            return self._finalize_get_by_offset(offset, data)
        else:
            return preparation

    async def get_by_index(self, index: int) -> Optional[AsyncModuleType]:
        offset = self._index_to_offset(index)
        if offset is None:
            return None
        record = await self._get_by_offset(offset)
        if record is None:
            raise IndexError(index)
        return record
