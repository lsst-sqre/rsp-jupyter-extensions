"""Exceptions for rsp-jupyter-extensions."""


class ClientError(Exception):
    """Class to indicate something went wrong with client construction."""


class ConfigError(Exception):
    """Class to indicate something went wrong with Config construction."""


class HierarchyError(Exception):
    """Class to indicate something went wrong with Hierarchy construction."""


class NotANotebookError(Exception):
    """Returned text from templated query is not a valid notebook."""


class TagError(Exception):
    """Class to indicate something went wrong with the image tag."""


class TokenNotAvailableError(RuntimeError):
    """No Gafaelfawr token is available."""


class UnimplementedQueryResolutionError(Exception):
    """Request for a query where the parameters are not resolvable."""


class UnknownDatasetError(Exception):
    """Request for a query from a dataset we have no TAP URL for."""


class UnknownInstanceError(Exception):
    """Class to indicate RSP Instance could not be determined."""


class UnsupportedQueryTypeError(Exception):
    """Request for a query of a type we don't know about."""


class UserEnvironmentError(Exception):
    """Class to indicate something went wrong with user environment."""
