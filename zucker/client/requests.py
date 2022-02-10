from typing import Mapping, Optional

from zucker.utils import JsonMapping

from .base import SyncClient


class RequestsClient(SyncClient):
    """Synchronous client implementation using `requests`_.

    .. _requests: https://docs.python-requests.org/en/latest/
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
        import requests

        super().__init__(
            base_url,
            username,
            password,
            client_platform=client_platform,
            verify_ssl=verify_ssl,
        )
        self._session = requests.Session()

    def raw_request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Mapping[str, str]] = None,
        data: Optional[JsonMapping] = None,
        json: Optional[JsonMapping] = None,
    ) -> tuple[int, JsonMapping]:
        response = self._session.request(
            method,
            f"{self.base_url}/rest/v11_5/{endpoint}",
            headers={
                "OAuth-Token": self._authentication[1],
                "Cache-Control": "no-cache",
            },
            verify=self._verify_ssl,
            params=params or {},
            data=data or {},
            json=json or {},
        )
        return response.status_code, response.json()
