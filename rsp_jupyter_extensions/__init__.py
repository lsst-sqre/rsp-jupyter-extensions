from jupyter_server.utils import url_path_join as ujoin

from .handlers.environment import EnvironmentHandler
from .handlers.execution import ExecutionHandler
from .handlers.ghostwriter import GhostwriterHandler
from .handlers.hub import HubHandler
from .handlers.query import QueryHandler
from .handlers.tutorials import TutorialsMenuHandler

try:
    from ._version import __version__
except ImportError:
    # Fallback when using the package in dev mode without installing
    # in editable mode with pip. It is highly recommended to install
    # the package from a stable release or in editable mode: https://pip.pypa.io/en/stable/topics/local-project-installs/#editable-installs
    import warnings

    warnings.warn(
        "Importing 'rsp_jupyter_extensions' outside a proper installation."
    )
    __version__ = "dev"


def _jupyter_labextension_paths() -> list[dict[str,str]]:
    return [{"src": "labextension", "dest": "rsp-jupyter-extensions"}]


def _jupyter_server_extension_points() -> list[dict[str, str]]:
    return [{"module": "rsp_jupyter_extensions"}]


def _setup_handlers(server_app) -> None:  # type: ignore
    """Sets up the route handlers to call the appropriate functionality."""
    web_app = server_app.web_app
    extmap = {
        r"/rubin/environment": EnvironmentHandler,
        r"/rubin/execution": ExecutionHandler,
        r"/rubin/ghostwriter($|/$|/.*)": GhostwriterHandler,
        r"/rubin/hub": HubHandler,
        r"/rubin/query($|/$|.*)": QueryHandler,
        r"/rubin/query": QueryHandler,
        r"/rubin/tutorials": TutorialsMenuHandler,
    }

    # add the baseurl to our paths...
    host_pattern = ".*$"
    base_url = web_app.settings["base_url"]
    # And now add the handlers.
    handlers = [(ujoin(base_url, x), extmap[x]) for x in extmap]
    server_app.log.info(f"RJE Handlers: {handlers}")
    web_app.add_handlers(host_pattern, handlers)


def _load_jupyter_server_extension(server_app) -> None:  # type: ignore
    """Registers the API handler to receive HTTP requests from the frontend extension.

    Parameters
    ----------
    server_app: jupyterlab.labapp.LabApp
        JupyterLab application instance
    """
    _setup_handlers(server_app)
    name = "rsp_jupyter_extensions"
    server_app.log.info(f"Registered {name} server extension")


# For backward compatibility with notebook server - useful for JupyterHub
load_jupyter_server_extension = _load_jupyter_server_extension
