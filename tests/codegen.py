import sys
from unittest.mock import patch


def test_inspection():
    @patch("zucker.SugarClient")
    class FakeClient:
        def __init__(self, base_url, username, password, **kwargs):
            assert base_url == "https://server"
            assert username == "username"
            assert password == "passsword"
            assert kwargs["client_platform"] == "theclient"

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