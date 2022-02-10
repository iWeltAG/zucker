from collections.abc import Mapping
from typing import Optional

from zucker.utils import JsonMapping, JsonType

from .base import AsyncClient


class AioClient(AsyncClient):
    """Asynchronous client implementation using `aiohttp`_.

    .. _aiohttp: https://docs.aiohttp.org/en/latest/index.html
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
        import aiohttp

        super().__init__(
            base_url,
            username,
            password,
            client_platform=client_platform,
            verify_ssl=verify_ssl,
        )

        self._session: Optional[aiohttp.ClientSession] = None

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def raw_request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Mapping[str, str]] = None,
        data: Optional[JsonMapping] = None,
        json: Optional[JsonMapping] = None,
    ) -> tuple[int, JsonType]:
        import aiohttp

        if self._session is None:
            self._session = aiohttp.ClientSession()
            # The following doesn't actually do anything at the moment, but that might
            # change in a future version of aiohttp.
            await self._session.__aenter__()

        async with self._session.request(
            method,
            f"{self.base_url}/rest/v11_5/{endpoint}",
            headers={
                "OAuth-Token": self._authentication[1],
                "Cache-Control": "no-cache",
            },
            verify_ssl=self._verify_ssl,
            params=params or None,
            data=data or None,
            json=json or None,
        ) as response:
            return response.status, (await response.json())
