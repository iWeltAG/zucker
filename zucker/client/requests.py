from typing import Optional

import requests

from zucker.exceptions import SugarError, ZuckerException
from zucker.utils import JsonMapping

from .base import SyncClient


class RequestsClient(SyncClient):
    """Synchronous client implementation using `requests`_.

    .. _requests: https://docs.python-requests.org/en/latest/
    """

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
            request = requests.post(
                f"{self.base_url}/rest/v11_5/{auth_endpoint}",
                headers={"Cache-Control": "no-cache"},
                verify=self._verify_ssl,
                data=auth_data,
            )
            if request.ok:
                self._finalize_authentication(request.json())
            else:
                raise ZuckerException(
                    f"{auth_job_name} failed with status code {request.status_code} "
                    f"and message {request.text!r}"
                )

        request = requests.request(
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

        if request.ok:
            return self._finalize_request(request.json())
        else:
            raise SugarError(request.status_code, request.json())
