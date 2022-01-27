from __future__ import annotations

import abc
import asyncio
import urllib.parse
from datetime import datetime, timedelta
from json import dumps as dump_json
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Iterator,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)

from zucker.exceptions import (
    InvalidSugarResponseError,
    SugarError,
    UnfetchedMetadataError,
    ZuckerException,
)
from zucker.utils import JsonMapping, JsonType, MutableJsonMapping, check_json_mapping

if TYPE_CHECKING:
    from zucker.model.module import AsyncModule, BoundModule, SyncModule  # noqa: F401

_T = TypeVar("_T")
_T1 = TypeVar("_T1")
_T2 = TypeVar("_T2")
_T3 = TypeVar("_T3")
_T4 = TypeVar("_T4")
_T5 = TypeVar("_T5")
_T6 = TypeVar("_T6")


class BaseClient(abc.ABC):
    """Connection handler that handles communicating with a SugarCRM instance.

    This is the main entry point for interfacing with models. After creating a new
    instance, the server's modules are available as attributes on the client. Concrete
    client implementations (for different transport mechanisms) should implement one of
    :class:`~SyncClient` or :class:`~AsyncClient`.
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        client_platform: str = "zucker",
        verify_ssl: bool = True,
    ):
        """Construct a client instance.

        This may take a few seconds, as it performs initial authentication as well as querying
        the server for metadata about it's configuration.

        :param base_url: The URL of the SugarCRM installation to connect to.
        :param username: Username to authenticate with.
        :param password: Password to authenticate with.
        :param client_platform: OAuth platform string.
        :param verify_ssl: Set this to false to disable verification of the server's SSL
            certificate. This should only be used while testing!
        """
        values = (base_url, username, password, client_platform)
        if any(not isinstance(value, str) for value in values):
            raise TypeError(
                "all relevant parameters must be provided to create a Sugar client"
            )
        if any(len(value) == 0 for value in values):
            raise ValueError(
                "all relevant parameters must be provided to create a Sugar client"
            )

        self.base_url = base_url

        # The authentication is stored as one of two tuple types, depending on the
        # current state:
        self._authentication: Union[
            # This is the initial configuration, holding the username and password.
            Tuple[Literal[False], str, str],
            # After the initial OAuth step has completed, this tuple is stored instead.
            # It contains the access token, the refresh token and an expiry timestamp,
            # in that order.
            Tuple[Literal[True], str, str, datetime],
        ] = (False, username, password)
        self._client_platform = client_platform
        self._verify_ssl = verify_ssl

        self._metadata: MutableJsonMapping = {}

    def __contains__(self, item: Union[str, Type[BoundModule[Any]]]) -> bool:
        """Check if the server supports a given module name."""
        from zucker.model.module import BoundModule

        if isinstance(item, type) and issubclass(item, BoundModule):
            return item._api_name in self.module_names
        elif isinstance(item, str):
            return item in self.module_names
        else:
            raise TypeError(
                f"contains checks on a SugarClient are only supported with strings and "
                f"Module classes, got {type(item)!r}"
            )

    @abc.abstractmethod
    def fetch_metadata(self, *types: str) -> Union[None, Awaitable[None]]:
        """Make sure server metadata for the given set of types is available."""

    def get_metadata_item(self, type_name: str) -> JsonMapping:
        """Return the cached value of a given metadata item.

        :param type_name: Name of the metadata's type, as defined by Sugar.
        :raise UnfetchedMetadataError: This error will be raised when the corresponding
            metadata has not been fetched yet. In that case, call :meth:`fetch_metadata`
            to populate the cache.
        """
        if type_name not in self._metadata:
            raise UnfetchedMetadataError(
                f"metadata field {type_name!r} is not available"
            )
        try:
            return check_json_mapping(self._metadata[type_name])
        except TypeError:
            raise InvalidSugarResponseError("got invalid server metadata")

    @property
    def module_names(self) -> Iterator[str]:
        """List of all modules that are available.

        This requires fetching the ``full_module_list`` metadata item.
        """
        full_module_list = self.get_metadata_item("full_module_list")
        assert isinstance(full_module_list, Mapping)

        yield from (
            name for name in full_module_list.keys() if not name.startswith("_")
        )

    @property
    def server_info(self) -> Tuple[str, str, str]:
        """Sever information tuple.

        This requires fetching the ``server_info`` metadata item.

        :return: A 3-tuple that follows the syntax (``flavor``, ``version``, ``build``).
        """
        server_info = self.get_metadata_item("server_info")
        assert isinstance(server_info, Mapping)

        flavor = server_info["flavor"]
        assert isinstance(flavor, str)

        version = server_info["version"]
        assert isinstance(version, str)

        build = server_info["build"]
        assert isinstance(build, str)

        return flavor, version, build

    @property
    def authenticated(self) -> bool:
        """Shows whether initial authentication with the server has already been
        performed.
        """
        return self._authentication[0]

    def _prepare_authentication(
        self,
    ) -> Optional[Tuple[str, str, Mapping[str, str]]]:
        """Build the payload currently required to process authentication.

        The output of this function will be one of:

        - ``None``, when authentication information is still valid
        - ``("initial authentication", str, dict)`` for the first authentication with
          username and password
        - ``("authentication token renewal", str, dict)`` for renewing an active token

        For the second and third outputs, the tuple contains the name of the action
        being performed (for error logging), the API endpoint and the ``data`` parameter
        that should be used for performing the authentication request.
        """
        if self._authentication[0] is True:
            # Initial OAuth has already happened. The token will be renewed.
            _, _, refresh_token, expire_timestamp = self._authentication
            if expire_timestamp > datetime.now() + timedelta(minutes=10):
                return None
            return (
                "authentication token renewal",
                "oauth2/token/",
                {
                    "grant_type": "refresh_token",
                    "client_id": "sugar",
                    "client_secret": "",
                    "refresh_token": refresh_token,
                    "platform": self._client_platform,
                },
            )
        else:
            # No initial authentication has happened yet. Retrieve the initial tokens.
            _, username, password = self._authentication
            return (
                "initial authentication",
                "oauth2/token/",
                {
                    "grant_type": "password",
                    "client_id": "sugar",
                    "client_secret": "",
                    "username": username,
                    "password": password,
                    "platform": self._client_platform,
                },
            )

    def _finalize_authentication(
        self, auth_job_name: str, response_code: int, data: Any
    ) -> None:
        """Process the result from the authentication call and save the required
        tokens."""
        if not (200 <= response_code < 300):
            raise ZuckerException(
                f"{auth_job_name} failed with status code {response_code}"
            )

        response_json = check_json_mapping(data)

        if (
            "access_token" not in response_json
            or "refresh_token" not in response_json
            or "expires_in" not in response_json
        ):
            raise InvalidSugarResponseError(
                "missing response_json fields from authentication result"
            )

        access_token = response_json["access_token"]
        refresh_token = response_json["refresh_token"]
        if not isinstance(access_token, str) or not isinstance(refresh_token, str):
            raise InvalidSugarResponseError(
                f"bad authentication data: expected token strings, got "
                f"{type(access_token)!r} and {type(refresh_token)!r}"
            )

        expires_in = response_json["expires_in"]
        if not isinstance(expires_in, (int, float)):
            raise InvalidSugarResponseError(
                f"bad authentication data: expected exipry timestamp as a number, got "
                f"{type(expires_in)!r}"
            )
        expire_timestamp = datetime.now() + timedelta(seconds=expires_in)

        self._authentication = (True, access_token, refresh_token, expire_timestamp)

    def _finalize_request(self, response_code: int, data: Any) -> JsonMapping:
        """Process the response from an API request and return a type-checked
        ``JsonMapping`` type.
        """
        try:
            response_json = check_json_mapping(data)
        except TypeError:
            raise InvalidSugarResponseError("got invalid JSON response from Sugar")
        if 200 <= response_code < 300:
            return response_json
        else:
            raise SugarError(response_code, response_json)

    @abc.abstractmethod
    def close(self) -> Union[None, Awaitable[None]]:
        """Perform cleanup operations.

        This method should be called when the client is no longer used. Further
        operations on the client or any of its modules are consider undefined behavior
        afterwards. Some clients may be able to reinitialize transparently after
        closing while others may be unusable.
        """

    @abc.abstractmethod
    def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Mapping[str, str]] = None,
        data: Optional[JsonMapping] = None,
        json: Optional[JsonMapping] = None,
    ) -> Union[JsonMapping, Awaitable[JsonMapping]]:
        """Handle a request to the CRM's REST API.

        This will make sure that authentication is set up and the correct URL is built.
        Parameters are akin to those defined by popular HTTP libraries (although not all
        are supported).

        :param method: HTTP verb to use.
        :param endpoint: Desired endpoint name (the part after `/rest/v??_?/`).
        :param params: Dictionary of query parameters to add to the URL.
        :param data: Request form data.
        :param json: Request body that will be JSON-encoded. This is mutually exclusive
            with ``data``.
        """


class SyncClient(BaseClient, abc.ABC):
    def close(self) -> None:
        pass

    @abc.abstractmethod
    def raw_request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Mapping[str, str]] = None,
        data: Optional[JsonMapping] = None,
        json: Optional[JsonMapping] = None,
    ) -> tuple[int, JsonMapping]:
        """Request handling method that should be overridden by client implementations.

        This takes the same parameters as :meth:`BaseClient.request`.

        :returns: A tuple containing the response's status code and the JSON object
            gotten from the API.
        """

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Mapping[str, str]] = None,
        data: Optional[JsonMapping] = None,
        json: Optional[JsonMapping] = None,
    ) -> JsonMapping:
        auth_payload = self._prepare_authentication()

        if auth_payload is not None:
            auth_job_name, auth_endpoint, auth_data = auth_payload
            response_code, response_json = self.raw_request(
                "post",
                auth_endpoint,
                data=auth_data,
            )
            self._finalize_authentication(auth_job_name, response_code, response_json)

        response_code, response_json = self.raw_request(
            method, endpoint, params=params, data=data, json=json
        )
        return self._finalize_request(response_code, response_json)

    def fetch_metadata(self, *types: str) -> None:
        """Make sure server metadata for the given set of types is available."""
        self._metadata.update(
            self.request(
                "get",
                "metadata",
                params={"type_filter": ",".join(types)},
            )
        )


class AsyncClient(BaseClient):
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        client_platform: str = "zucker",
        verify_ssl: bool = True,
    ):
        super().__init__(
            base_url,
            username,
            password,
            client_platform=client_platform,
            verify_ssl=verify_ssl,
        )

        self._handle_bulk: Optional[
            Callable[[JsonMapping], Awaitable[tuple[int, JsonMapping]]]
        ] = None

    async def close(self) -> None:
        pass

    @abc.abstractmethod
    async def raw_request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Mapping[str, str]] = None,
        data: Optional[JsonMapping] = None,
        json: Optional[JsonMapping] = None,
    ) -> tuple[int, JsonType]:
        """Request handling method that should be overridden by client implementations.

        This takes the same parameters as :meth:`BaseClient.request`.

        :returns: A tuple containing the response's status code and the JSON object
            gotten from the API.
        """

    async def _ensure_authentication(self) -> None:
        auth_payload = self._prepare_authentication()

        if auth_payload is not None:
            auth_job_name, auth_endpoint, auth_data = auth_payload
            response_code, response_json = await self.raw_request(
                "post",
                auth_endpoint,
                data=auth_data,
            )
            self._finalize_authentication(auth_job_name, response_code, response_json)

    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Mapping[str, str]] = None,
        data: Optional[JsonMapping] = None,
        json: Optional[JsonMapping] = None,
        allow_bulk: bool = True,
    ) -> JsonMapping:
        response_code: int
        response_json: JsonMapping

        if self._handle_bulk is not None and allow_bulk:
            # Important: when making changes, make sure to not await anything in this
            # branch except the final self._handle bulk so we don't get any race
            # conditions (we don't assume thread-safety, however).

            if data is not None:
                raise RuntimeError(
                    "data argument for requests is not supported in bulk contexts"
                )

            url = f"/v11_5/{endpoint}"
            if params is not None:
                url += "?"
                url += "&".join(
                    f"{urllib.parse.quote_plus(key)}={urllib.parse.quote_plus(value)}"
                    for key, value in params.items()
                )
            request_definition = dict(url=url, method=method.upper())
            if json is not None:
                request_definition["data"] = dump_json(json)

            response_code, response_json = await self._handle_bulk(request_definition)
        else:
            await self._ensure_authentication()

            response_code, response_raw_json = await self.raw_request(
                method, endpoint, params=params, data=data, json=json
            )
            response_json = check_json_mapping(response_raw_json)

        return self._finalize_request(response_code, response_json)

    # Typing for bulk() is a bit stupid because the Python typing system doesn't (yet)
    # support unknown-length type variable lists. See here:
    # https://github.com/python/typeshed/pull/1550
    # https://github.com/python/typeshed/blob/master/stdlib/asyncio/tasks.pyi#L44-L47

    @overload
    async def bulk(self, action_1: Awaitable[_T1], /) -> tuple[_T1]:
        ...

    @overload
    async def bulk(
        self, action_1: Awaitable[_T1], action_2: Awaitable[_T2], /
    ) -> tuple[_T1, _T2]:
        ...

    @overload
    async def bulk(
        self,
        action_1: Awaitable[_T1],
        action_2: Awaitable[_T2],
        action_3: Awaitable[_T3],
        /,
    ) -> tuple[_T1, _T2, _T3]:
        ...

    @overload
    async def bulk(
        self,
        action_1: Awaitable[_T1],
        action_2: Awaitable[_T2],
        action_3: Awaitable[_T3],
        action_4: Awaitable[_T4],
        /,
    ) -> tuple[_T1, _T2, _T3, _T4]:
        ...

    @overload
    async def bulk(
        self,
        action_1: Awaitable[_T1],
        action_2: Awaitable[_T2],
        action_3: Awaitable[_T3],
        action_4: Awaitable[_T4],
        action_5: Awaitable[_T5],
        /,
    ) -> tuple[_T1, _T2, _T3, _T4, _T5]:
        ...

    @overload
    async def bulk(
        self,
        action_1: Awaitable[_T1],
        action_2: Awaitable[_T2],
        action_3: Awaitable[_T3],
        action_4: Awaitable[_T4],
        action_5: Awaitable[_T5],
        action_6: Awaitable[_T6],
        /,
    ) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6]:
        ...

    @overload
    async def bulk(self, *actions: Awaitable[Any]) -> tuple[Any, ...]:
        ...

    async def bulk(self, *actions: Awaitable[Any]) -> tuple[Any, ...]:
        """Run a sequence of actions that require server communication together.

        This will use Sugar's `Bulk API`_ to batch all actions together and send them
        as a single HTTP request. It works similarly to :func:`asyncio.gather` in that
        this method will resolve once the result for all provided awaitables is
        available and return them as a tuple. You can also use this method to gather
        together multiple awaitables where only one of them uses the server. If an
        action doesn't resolve after the first request (for example because it needs a
        second one), a second batch will be started.

        Do not use this is threaded environments -- the implementation is not
        thread-safe.

        .. _Bulk API: https://support.sugarcrm.com/Documentation/Sugar_Developer/Sugar_Developer_Guide_11.3/Integration/Web_Services/REST_API/Endpoints/bulk_POST/
        """
        # These dictionaries store the prepared requests that should be sent. Each
        # definition contains a JSON object in the form accepted by the bulk Sugar API
        # (see the link in this method's docstring). Every request that gets started
        # gets a unique key (an int). Next to the definition, we also store an Event
        # that will get set once a response is available. The first dictionary here will
        # hold all requests that are currently waiting to be processed. The second
        # contains responses for those requests where a /bulk call has returned data.
        next_key = 0
        request_definitions = dict[int, tuple[JsonMapping, asyncio.Event]]()
        responses = dict[int, tuple[int, JsonMapping]]()

        # This event will be set whenever the number of waiting requests change.
        counting_event = asyncio.Event()

        async def handle_bulk(
            request_definition: JsonMapping,
        ) -> tuple[int, JsonMapping]:
            """Callback for handling bulk requests. This is called from the actual
            request() method and will queue the request, wait for the corresponding
            batch is done and then return the result."""
            nonlocal next_key

            request_event = asyncio.Event()

            # This shouldn't create any race conditions because we are not targeting
            # thread safety (same goes for the counting stuff further down):
            request_key = next_key
            next_key += 1
            request_definitions[request_key] = request_definition, request_event
            counting_event.set()

            await request_event.wait()

            try:
                return responses.pop(request_key)
            finally:
                counting_event.set()

        self._handle_bulk = handle_bulk
        action_tasks = [asyncio.create_task(action) for action in actions]
        for task in action_tasks:
            task.add_done_callback(lambda *_: counting_event.set())

        # This loop will run as long as at least on action hasn't returned yet and
        # therefore may still be waiting on a request. Further, that action may even
        # perform more requests after that. We handle that case by sending requests
        # off in batches - one in each round of this loop.
        while (
            done_task_count := sum(1 for task in action_tasks if task.done())
        ) != len(actions):
            # Wait until all tasks have either completed (for those that don't actually
            # use the server) or are waiting for the actual server request to start (and
            # have therefore registered themselves in the request_definitions list). In
            # most calls, the latter will probably be the case, but we want to block
            # this method when a completely unrelated awaitable gets passed.
            if len(request_definitions) < len(actions) - done_task_count:
                await counting_event.wait()
                counting_event.clear()
                continue

            # Now, we are in a state where every remaining (as in: not done) task is
            # waiting for a request to complete. That means we can now collect them from
            # the definitions dictionary, run them all through the /bulk API endpoint
            # and split the results back up:

            await self._ensure_authentication()

            request_keys = list(request_definitions.keys())
            request_events: list[asyncio.Event] = [
                request_definitions[key][1] for key in request_keys
            ]
            response_code, response_json = await self.raw_request(
                "post",
                "/bulk",
                json=dict(
                    requests=[request_definitions[key][0] for key in request_keys]
                ),
            )
            request_definitions.clear()
            if not isinstance(response_json, Sequence):
                raise InvalidSugarResponseError(
                    f"expected list from bulk API, got {type(response_json)!r}"
                )
            if not len(response_json) == len(request_keys):
                raise InvalidSugarResponseError(
                    f"expected list of length {len(request_keys)} from bulk API, got "
                    f"length {len(response_json)}"
                )

            for key, item in zip(request_keys, response_json):
                if not isinstance(item, Mapping):
                    raise InvalidSugarResponseError(
                        f"expected dictionary in bulk API list, got {type(item)!r}"
                    )
                if (
                    "contents" not in item
                    or not isinstance(item["contents"], Mapping)
                    or "status" not in item
                    or not isinstance(item["status"], int)
                ):
                    raise InvalidSugarResponseError(
                        "got invalid dictionary layout from bulk API"
                    )
                check_json_mapping(item["contents"])
                responses[key] = (item["status"], item["contents"])

            # When these events are set, handle_bulk() will pick it up and take the
            # correct response out of the 'responses' dictionary:
            for event in request_events:
                event.set()

        return await asyncio.gather(*action_tasks)  # type: ignore

    async def fetch_metadata(self, *types: str) -> None:
        """Make sure server metadata for the given set of types is available."""
        self._metadata.update(
            await self.request(
                "get",
                "metadata",
                params={"type_filter": ",".join(types)},
            )
        )
