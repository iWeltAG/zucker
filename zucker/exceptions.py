from typing import Any


class ZuckerException(Exception):
    """Base class for all errors raised by Zucker."""


class WrongParadigmError(ZuckerException):
    """Raised when the sync / async paradigms clash."""


class WrongClientError(ZuckerException):
    """Raised when an operation receives an unexpected client instance."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(
            "Related field was accessed from a different client that the defined "
            "module. Make sure that both the module the field is defined in as the "
            "referring module are bound to the same client."
        )


class SugarError(ZuckerException):
    """Base error that is raised when the Sugar API responds with a failure status
    code.
    """

    def __init__(self, status_code: int, body: Any, *args: Any):
        try:
            error_message = str(body["error_message"])
        except TypeError:
            error_message = str(body)
        super(SugarError, self).__init__(error_message, *args)
        self.status_code = status_code


class InvalidSugarResponseError(ZuckerException):
    """Exceptions of this type are raised when the Sugar server sends an invalid
    response.
    """


class UnfetchedMetadataError(ZuckerException):
    """Raised when client metadata has not been fetched yet."""


class UnsavedRecordError(ZuckerException):
    """Raised when mutations are requested on a record that doesn't have a server-side
    ID yet.
    """
