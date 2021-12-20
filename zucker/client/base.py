from __future__ import annotations

import abc
from datetime import datetime, timedelta
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Iterator,
    Literal,
    Mapping,
    Optional,
    Tuple,
    Type,
    Union,
)

from zucker.exceptions import InvalidSugarResponseError, UnfetchedMetadataError
from zucker.utils import JsonMapping, MutableJsonMapping, check_json_mapping

if TYPE_CHECKING:
    from zucker.model.module import AsyncModule, BoundModule, SyncModule  # noqa: F401


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

    def _finalize_authentication(self, data: Any) -> None:
        """Process the result from the authentication call and save the required
        tokens."""
        response = check_json_mapping(data)

        if (
            "access_token" not in response
            or "refresh_token" not in response
            or "expires_in" not in response
        ):
            raise InvalidSugarResponseError(
                "missing response fields from authentication result"
            )

        access_token = response["access_token"]
        refresh_token = response["refresh_token"]
        if not isinstance(access_token, str) or not isinstance(refresh_token, str):
            raise InvalidSugarResponseError(
                f"bad authentication data: expected token strings, got "
                f"{type(access_token)!r} and {type(refresh_token)!r}"
            )

        expires_in = response["expires_in"]
        if not isinstance(expires_in, (int, float)):
            raise InvalidSugarResponseError(
                f"bad authentication data: expected exipry timestamp as a number, got "
                f"{type(expires_in)!r}"
            )
        expire_timestamp = datetime.now() + timedelta(seconds=expires_in)

        self._authentication = (True, access_token, refresh_token, expire_timestamp)

    def _finalize_request(self, data: Any) -> JsonMapping:
        """Process the response from an API request and return a type-checked
        ``JsonMapping`` type.
        """
        try:
            return check_json_mapping(data)
        except TypeError:
            raise InvalidSugarResponseError("got invalid JSON response from Sugar")

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
        params: Optional[JsonMapping] = None,
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
    def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[JsonMapping] = None,
        data: Optional[JsonMapping] = None,
        json: Optional[JsonMapping] = None,
    ) -> JsonMapping:
        ...

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
    async def close(self) -> None:
        pass

    @abc.abstractmethod
    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[JsonMapping] = None,
        data: Optional[JsonMapping] = None,
        json: Optional[JsonMapping] = None,
    ) -> JsonMapping:
        ...

    async def fetch_metadata(self, *types: str) -> None:
        """Make sure server metadata for the given set of types is available."""
        self._metadata.update(
            await self.request(
                "get",
                "metadata",
                params={"type_filter": ",".join(types)},
            )
        )
