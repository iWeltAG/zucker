from .utils import JsonMapping


class ZuckerException(Exception):
    """Base class for all errors raised by Zucker."""


class WrongParadigmError(ZuckerException):
    """Raised when the sync / async paradigms clash."""


class WrongClientError(ZuckerException):
    """Raised when an operation receives an unexpected client instance."""


class SugarError(ZuckerException):
    """Base error that is raised when the Sugar API responds with a failure status
    code.
    """

    def __init__(self, status_code: int, body: JsonMapping, *args):
        assert "error_message" in body
        super(SugarError, self).__init__(body["error_message"], *args)
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
