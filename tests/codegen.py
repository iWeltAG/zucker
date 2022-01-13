import sys
from typing import Any
from unittest.mock import patch


def test_inspection() -> None:
    @patch("zucker.SugarClient")
    class FakeClient:
        def __init__(
            self,
            base_url: str,
            username: str,
            password: str,
            *,
            client_platform: str,
            **kwargs: Any,
        ):
            assert base_url == "https://server"
            assert username == "username"
            assert password == "passsword"
            assert client_platform == "theclient"

    args = [
        sys.argv[0],
        "-b",
        "https://server",
        "-u",
        "username",
        "-c",
        "theclient",
        "-P",
        "inspect",
    ]
    with patch.object(sys, "argv", args):
        pass
