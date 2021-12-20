from typing import TYPE_CHECKING, Optional

from zucker.exceptions import SugarError, ZuckerException
from zucker.utils import JsonMapping

from .base import SyncClient


class RequestsClient(SyncClient):
    """Synchronous client implementation using `requests`_.

    .. _requests: https://docs.python-requests.org/en/latest/
    """

    def __init__(self, *args, **kwargs):
        import requests

        super().__init__(*args, **kwargs)
        self._session = requests.Session()

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[JsonMapping] = None,
        data: Optional[JsonMapping] = None,
        json: Optional[JsonMapping] = None,
    ) -> JsonMapping:
        auth_payload = self._prepare_authentication()
        if auth_payload is not None:
            auth_job_name, auth_endpoint, auth_data = auth_payload
            response = self._session.request(
                # We use .request("post") instead of .post() here because that's easier
                # to test.
                "post",
                f"{self.base_url}/rest/v11_5/{auth_endpoint}",
                headers={"Cache-Control": "no-cache"},
                verify=self._verify_ssl,
                data=auth_data,
            )
            if response.ok:
                self._finalize_authentication(response.json())
            else:
                raise ZuckerException(
                    f"{auth_job_name} failed with status code {response.status_code} "
                    f"and message {response.text!r}"
                )

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

        if response.ok:
            return self._finalize_request(response.json())
        else:
            raise SugarError(response.status_code, response.json())
