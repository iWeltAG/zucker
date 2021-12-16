import argparse
import sys
from getpass import getpass
from typing import Optional, Sequence, Union

from zucker.client import RequestsClient

from .inspect import run_inspect


class PromptPasswordAction(argparse.Action):
    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("nargs", 0)
        super().__init__(*args, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Union[str, Sequence[str], None],
        option_string: Optional[str] = None,
    ) -> None:
        if option_string in self.option_strings:
            if getattr(namespace, self.dest, None) is not None:
                parser.error(
                    "plaintext and prompt password options are mutually exclusive"
                )
            setattr(namespace, self.dest, getpass())


def run_from_command_line() -> None:
    parser = argparse.ArgumentParser(
        description="Automatically generate zucker model classes from a remote Sugar "
        "CRM instance.",
    )
    subparsers = parser.add_subparsers(title="subcommands")

    parser.add_argument(
        "-b",
        "--base-url",
        dest="base_url",
        metavar="URL",
        required=True,
        help="base URL of the Sugar CRM server",
    )
    parser.add_argument(
        "-c",
        "--client-platform",
        dest="client_platform",
        metavar="PLATFORM",
        default="zucker",
        help="client platform on the server",
    )
    parser.add_argument(
        "-u",
        "--username",
        dest="username",
        help="username to use for authentication",
    )
    parser.add_argument(
        "--plaintext-password",
        dest="password",
        help="plaintext password to use for authentication (consider using -P instead)",
    )
    parser.add_argument(
        "-P",
        "--prompt-password",
        dest="password",
        action=PromptPasswordAction,
        help="prompt for authentication password",
    )
    parser.add_argument(
        "--disable-ssl-verification",
        dest="verify_ssl",
        action="store_false",
        default=True,
        help="disable SSL certificate verification",
    )

    inspect_parser = subparsers.add_parser(
        "inspect",
        description="Build a list of the server's data model. This can be used to "
        "manually find the relevant fields.",
        help="extract the data model for manual inspection",
    )
    inspect_parser.set_defaults(callable=run_inspect)

    args = parser.parse_args()

    if getattr(args, "password", None) is None or len(args.password) == 0:
        parser.error("no authentication password was provided")
    if getattr(args, "callable", None) is None:
        parser.print_help()
        sys.exit(2)

    client = RequestsClient(
        **{
            key: getattr(args, key)
            for key in (
                "base_url",
                "username",
                "password",
                "client_platform",
                "verify_ssl",
            )
        }
    )
    args.callable(client, **args.__dict__)
