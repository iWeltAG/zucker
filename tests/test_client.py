from functools import partial
from typing import Callable, Optional
from uuid import uuid4

import pytest
import requests

from zucker import RequestsClient, SugarError, model
from zucker.client import SyncClient


class MockResponse:
    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return self.data


HandlerType = Callable[[str, str], Optional[MockResponse]]


@pytest.fixture
def fake_server(monkeypatch) -> Callable[[HandlerType], None]:
    handler: Optional[HandlerType] = None

    def set_handler(handler_callable: HandlerType):
        nonlocal handler
        handler = handler_callable

    def fake_request(request_method, path, **kwargs):
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

    monkeypatch.setattr(requests, "request", fake_request)
    for method in ("get", "post"):
        monkeypatch.setattr(requests, method, partial(fake_request, method))

    return set_handler


@pytest.fixture
def authenticated_client(monkeypatch) -> SyncClient:
    client = RequestsClient("http://base", "user", "pass")

    def fake_authentication_payload():
        return None

    monkeypatch.setattr(client, "_prepare_authentication", fake_authentication_payload)

    return client


def test_missing_parameters():
    with pytest.raises(ValueError):
        RequestsClient("http://base", "user", "")
    with pytest.raises(ValueError):
        RequestsClient("http://base", "", "pass")
    with pytest.raises(ValueError):
        RequestsClient("", "user", "pass")


def test_authentication_and_request(fake_server):
    access_token = None
    refresh_token = None

    def handle_request(method, path, data, headers, **kwargs):
        nonlocal access_token, refresh_token

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

    fake_server(handle_request)

    client = RequestsClient(
        "http://base", "testuser", "testpassword", client_platform="testplatform"
    )
    assert not client.authenticated
    assert client.request("get", "notaroute")["ping"] == "pong"
    assert client.authenticated

    with pytest.raises(SugarError) as error:
        client.request("get", "errorroute")
    assert error.value.status_code == 500
    assert "theerror" in str(error)


def test_metadata(authenticated_client: SyncClient, fake_server):
    server_flavor = "PRO"
    server_version = "9.0.1"
    server_build = "176"

    def handle_request(method, path, **kwargs):
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

    fake_server(handle_request)
    client = authenticated_client
    client.fetch_metadata("server_info", "full_module_list")

    assert client.server_info == (server_flavor, server_version, server_build)

    class A(client.Module):
        pass

    assert "A" in client
    assert A in client
    assert list(client.module_names) == ["A", "B", "C"]
