import asyncio
from functools import partial
from typing import Any, Awaitable, Callable, Mapping, Optional, Protocol, Union
from uuid import uuid4

import aiohttp
import pytest
import requests

from zucker import AioClient, RequestsClient, SugarError, model
from zucker.client import AsyncClient, SyncClient
from zucker.utils import JsonMapping, JsonType


class MockResponse:
    def __init__(self, data: JsonType, status_code: int = 200):
        self.data = data
        self.status_code = status_code

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    async def async_json(self) -> JsonType:
        return self.data

    def json(self) -> Union[JsonType, Awaitable[JsonType]]:
        try:
            asyncio.get_running_loop()
            return self.async_json()
        except RuntimeError:
            return self.data


class HandlerType(Protocol):
    def __call__(
        self,
        method: str,
        path: str,
        *,
        data: JsonType,
        headers: JsonMapping,
        **kwargs: Any,
    ) -> Optional[MockResponse]:
        pass


FakeServer = Callable[[HandlerType], None]


@pytest.fixture
def fake_server(monkeypatch: pytest.MonkeyPatch) -> FakeServer:
    handler: Optional[HandlerType] = None

    def set_handler(handler_callable: HandlerType) -> None:
        nonlocal handler
        handler = handler_callable

    def fake_request(
        self: Any, request_method: str, path: str, **kwargs: Any
    ) -> MockResponse:
        kwargs.setdefault("headers", {})
        kwargs.setdefault("data", {})

        if handler is None:
            raise RuntimeError(
                "Did not provide a handler to the fake_server fixture. Make sure you "
                "call the fixture with a method that has the same signature as "
                "requests.request."
            )

        result = handler(request_method, path, **kwargs)
        if result is not None:
            return result
        else:
            raise RuntimeError(f"requesting non-mocked path: {path!r} ({method})")

    async def async_fake_request(
        self: Any, request_method: str, path: str, **kwargs: Any
    ) -> MockResponse:
        return fake_request(None, request_method, path, **kwargs)

    monkeypatch.setattr(requests.Session, "request", fake_request)
    for method in ("get", "post"):
        monkeypatch.setattr(requests, method, partial(fake_request, method))
    monkeypatch.setattr(aiohttp.ClientSession, "request", async_fake_request)

    return set_handler


@pytest.fixture
def authenticated_sync_client(monkeypatch: pytest.MonkeyPatch) -> SyncClient:
    client = RequestsClient("http://base", "user", "pass")

    def fake_authentication_payload() -> None:
        return None

    monkeypatch.setattr(client, "_prepare_authentication", fake_authentication_payload)

    return client


@pytest.fixture
def authenticated_async_client(monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    client = AioClient("http://base", "user", "pass")

    def fake_authentication_payload() -> None:
        return None

    monkeypatch.setattr(client, "_prepare_authentication", fake_authentication_payload)

    return client


def test_missing_parameters() -> None:
    with pytest.raises(ValueError):
        RequestsClient("http://base", "user", "")
    with pytest.raises(ValueError):
        RequestsClient("http://base", "", "pass")
    with pytest.raises(ValueError):
        RequestsClient("", "user", "pass")


def test_authentication_and_request(fake_server: FakeServer) -> None:
    access_token = None
    refresh_token = None

    def handle_request(
        method: str,
        path: str,
        data: JsonType,
        headers: JsonMapping,
        **kwargs: Any,
    ) -> Optional[MockResponse]:
        nonlocal access_token, refresh_token
        assert isinstance(data, Mapping)

        if method == "post" and path == "http://base/rest/v11_5/oauth2/token/":
            assert data["client_id"] == "sugar"
            assert data["platform"] == "testplatform"
            if data["grant_type"] == "password":
                assert data["username"] == "testuser"
                assert data["password"] == "testpassword"
            elif data["grant_type"] == "refresh_token":
                assert data["refresh_token"] == refresh_token

            access_token = str(uuid4())
            refresh_token = str(uuid4())
            return MockResponse(
                {
                    "access_token": access_token,
                    "expires_in": 10,
                    "token_type": "bearer",
                    "scope": None,
                    "refresh_token": refresh_token,
                    "refresh_expires_in": 1209600,
                    "download_token": str(uuid4()),
                }
            )

        assert access_token is not None and headers["OAuth-Token"] == access_token

        if method == "get" and path == "http://base/rest/v11_5/notaroute":
            return MockResponse({"ping": "pong"})

        elif method == "get" and path == "http://base/rest/v11_5/errorroute":
            return MockResponse({"error_message": "theerror"}, 500)

        return None

    fake_server(handle_request)

    client = RequestsClient(
        "http://base", "testuser", "testpassword", client_platform="testplatform"
    )
    assert not client.authenticated
    assert client.request("get", "notaroute")["ping"] == "pong"
    client = client
    assert client.authenticated

    # The following statement would be unreachable because of the two
    # client.authenticated assertions above.
    with pytest.raises(SugarError) as error:
        client.request("get", "errorroute")
    assert error.value.status_code == 500
    assert "theerror" in str(error)


def test_metadata(
    authenticated_sync_client: SyncClient, fake_server: FakeServer
) -> None:
    server_flavor = "PRO"
    server_version = "9.0.1"
    server_build = "176"

    def handle_request(method: str, path: str, **kwargs: Any) -> Optional[MockResponse]:
        if method == "get" and path == "http://base/rest/v11_5/metadata":
            return MockResponse(
                {
                    "server_info": {
                        "flavor": server_flavor,
                        "version": server_version,
                        "build": server_build,
                        "marketing_version": "Spring '19",
                        "product_name": "SugarCRM Professional",
                        "site_id": "abc123",
                    },
                    "full_module_list": {
                        "A": "A",
                        "B": "B",
                        "C": "C",
                        "_hash": str(uuid4()),
                    },
                    "_hash": str(uuid4()),
                }
            )

        return None

    fake_server(handle_request)
    client = authenticated_sync_client
    client.fetch_metadata("server_info", "full_module_list")

    assert client.server_info == (server_flavor, server_version, server_build)

    class A(model.SyncModule, client=client):
        pass

    assert "A" in client
    assert A in client
    assert list(client.module_names) == ["A", "B", "C"]
