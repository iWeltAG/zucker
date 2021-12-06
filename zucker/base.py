from typing import Protocol


class BaseClient(Protocol):
    def request(self, method: str, endpoint: str, **kwargs) -> dict:
        ...
