from typing import Optional

from zucker.exceptions import SugarError, ZuckerException
from zucker.utils import JsonMapping

from .base import AsyncClient


class AioClient(AsyncClient):
    """Asynchronous client implementation using `aiohttp`_.

    .. _aiohttp: https://docs.aiohttp.org/en/latest/index.html
    """

    def __init__(self, *args, **kwargs):
        import aiohttp

        super().__init__(*args, **kwargs)

        self._session: Optional[aiohttp.ClientSession] = None

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[JsonMapping] = None,
        data: Optional[JsonMapping] = None,
        json: Optional[JsonMapping] = None,
    ) -> JsonMapping:
        import aiohttp

        if self._session is None:
            self._session = aiohttp.ClientSession()
            # The following doesn't actually do anything at the moment, but that might
            # change in a future version of aiohttp.
            await self._session.__aenter__()

        auth_payload = self._prepare_authentication()
        if auth_payload is not None:
            auth_job_name, auth_endpoint, auth_data = auth_payload

            async with self._session.post(
                f"{self.base_url}/rest/v11_5/{auth_endpoint}",
                headers={"Cache-Control": "no-cache"},
                verify_ssl=self._verify_ssl,
                data=auth_data,
            ) as request:
                if request.ok:
                    self._finalize_authentication(await request.json())
                else:
                    raise ZuckerException(
                        f"{auth_job_name} failed with status code {request.status} "
                        f"and message {request.text!r}"
                    )

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
        ) as request:
            if request.ok:
                return self._finalize_request(await request.json())
            else:
                raise SugarError(request.status, await request.json())
