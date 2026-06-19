"""Register handlers for RSP extension routes."""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import jupyterlab
import jupyter_server
from jupyter_server.base.handlers import JupyterHandler
from jupyter_server.services.contents.filemanager import (
    AsyncFileContentsManager,
    ContentsManager
)
from jupyter_server_documents.rooms.yroom_manager import YRoomManager

from jupyter_core.paths import jupyter_data_dir
from jupyter_server.utils import url_path_join as ujoin

from .handlers.abnormal import AbnormalStartupHandler
from .handlers.collab_filebrowser import (
    COLLAB_SETTINGS_KEY,
    CollabContentsHandler,
    CollabCheckpointsHandler,
    CollabModifyCheckpointsHandler,
    CollabTrustNotebooksHandler,
    build_collab_ydoc_classes,
)
from .handlers.config import ConfigHandler
from .handlers.config_generator import ConfigGenerator
from .handlers.execution import ExecutionHandler
from .handlers.ghostwriter import GhostwriterHandler
from .handlers.hub import HubHandler
from .handlers.pdfexport import PDFExportHandler
from .handlers.serviceinfo import ServiceInfoHandler
from .handlers.tapquery import TAPQueryHandler
from .handlers.tutorials import TutorialsMenuHandler

try:
    from ._version import __version__
except ImportError:
    # Fallback when using the package in dev mode without installing
    # in editable mode with pip. It is highly recommended to install
    # the package from a stable release or in editable mode: https://pip.pypa.io/en/stable/topics/local-project-installs/#editable-installs
    import warnings

    warnings.warn(
        "Importing 'rsp_jupyter_extensions' outside a proper installation.",
        stacklevel=2
    )
    __version__ = "dev"

def _jupyter_labextension_paths() -> list[dict[str,str]]:
    return [{"src": "labextension", "dest": "rsp-jupyter-extensions"}]


def _jupyter_server_extension_points() -> list[dict[str, str]]:
    return [{"module": "rsp_jupyter_extensions"}]


def _setup_handlers(server_app: jupyter_server.serverapp.ServerApp
                    ) -> None:
    """Sets up the route handlers to call the appropriate functionality."""

    regex = {
        "path": r"(?P<path>(?:(?:/[^/]+)+|/?))",
        "checkpoint_id": r"(?P<checkpoint_id>[\w-]+)"
    }
    web_app = server_app.web_app
    _cfg_gen = ConfigGenerator()
    _cfg = _cfg_gen.generate_config()
    collab_dir = _cfg.collab_dir
    cm: AsyncFileContentsManager | None = None
    if collab_dir:
        # ensure it points at a directory
        collab_path = Path(collab_dir)
        if collab_path.is_dir():
            cm = AsyncFileContentsManager(
                root_dir=collab_dir,
                allow_hidden=getattr(server_app.contents_manager,
                                     "allow_hidden", False)
            )
            cm.log = server_app.log
            cm.parent = server_app
            _check_link(collab_path, cm.log)
    web_app.settings[COLLAB_SETTINGS_KEY] = cm
    extmap = {
        r"/rubin/abnormal": AbnormalStartupHandler,
        r"/rubin/config": ConfigHandler,
        r"/rubin/execution": ExecutionHandler,
        r"/rubin/ghostwriter($|/$|/.*)": GhostwriterHandler,
        r"/rubin/hub": HubHandler,
        r"/rubin/pdfexport": PDFExportHandler,
        r"/rubin/queries($|/$|.*)": TAPQueryHandler,
        r"/rubin/serviceinfo": ServiceInfoHandler,
        r"/rubin/tutorials": TutorialsMenuHandler,
    }
    if cm:
        extmap.update(
            {
                r"/rubin/collab/checkpoints": CollabCheckpointsHandler,
                ("/rubin/collab/checkpoints/"
                 rf"{regex['checkpoint_id']}"): CollabModifyCheckpointsHandler,
                (rf"/rubin/collab{regex['path']}"
                 "/trust"): CollabTrustNotebooksHandler,
                rf"/rubin/collab{regex['path']}": CollabContentsHandler,
            }
        )
    # add the baseurl to our paths...
    host_pattern = ".*$"
    base_url = web_app.settings["base_url"]
    # And now add the handlers.
    handlers = [(ujoin(base_url, x), extmap[x]) for x in extmap]
    hnames = [(ujoin(base_url, x), extmap[x].__name__) for x in extmap]
    server_app.log.info(f"RJE Handlers: {hnames}")
    web_app.add_handlers(host_pattern, handlers)
    if cm and collab_dir:  # mypy can't tell cm is contingent on collab_dir
        ydoc_classes = build_collab_ydoc_classes()
        ydoc_handlers = _extract_ydoc_handlers(extmap,regex)
        if ydoc_classes is not None:
            _register_collab_ydoc(
                server_app = server_app,
                collab_cm = cm,
                prefix = ujoin(base_url, "/rubin/collab"),
                handlers = ydoc_handlers,
                ydoc_classes = ydoc_classes,
                collab_dir = collab_dir,
            )

def _check_link(collab_path:Path, log: logging.Logger) -> None:
    homedir = Path(os.environ.get("HOME", ""))
    local_link = homedir / ".collab" / collab_path.name
    if local_link.is_symlink():
        link=local_link.readlink()
        if link != collab_path:
            log.warning(f"{local_link!s} points to {link!s}, not "
                        f"{collab_path!s}")
        return
    if local_link.exists():
        log.warning(f"{local_link!s} exists but is not a symlink to"
                             f" {collab_path!s}")
        return
    local_link.parent.mkdir(exist_ok=True)
    log.info(f"Creating link from {collab_path!s} to {local_link!s}")
    try:
        local_link.symlink_to(collab_path)
    except Exception:
        log.exception("Link creation failed")


def _extract_ydoc_handlers(
    extmap: dict[str, type[JupyterHandler]],
    regex: dict[str,str]
) -> list[tuple[str,type[JupyterHandler]]]:
    retval: list[tuple[str, type[JupyterHandler]]] = []
    for reg in (
        rf"/rubin/collab/checkpoints/{regex['checkpoint_id']}",
        r"/rubin/collab/checkpoints",
        rf"/rubin/collab{regex['path']}"
    ):
        retval.append( (reg, extmap[reg] ) )
    return retval

def _register_collab_ydoc(
    *,
    server_app: jupyter_server.serverapp.ServerApp,
    collab_cm: ContentsManager,
    prefix: str,
    handlers: list[tuple],
    ydoc_classes: dict[str, Any],
    collab_dir: str
) -> None:
    """Instantiate and register all collab YDoc collaboration objects.

    Mutates ``handlers`` in-place to append the collaboration routes.
    """
    LocalFileIdManager = ydoc_classes["LocalFileIdManager"]
    CollabYRoomManager = ydoc_classes["CollabYRoomManager"]
    CollabYRoomWebsocket = ydoc_classes["CollabYRoomWebsocket"]
    CollabFileIDIndexHandler = ydoc_classes["CollabFileIDIndexHandler"]

    # File-ID manager: isolated SQLite database, root = collab only.
    # Keeping the root there prevents the database from escaping into
    # the wider filesystem (for instance, /rubin can easily have millions to
    # billions of files).
    db_path = str(Path(jupyter_data_dir()) / "collab_file_ids.db")
    collab_fileid_manager = LocalFileIdManager(
	root_dir=collab_dir,
	db_path=db_path,
    )
    collab_fileid_manager.log = server_app.log

    # YRoomManager: manages all collaborative rooms for /collab files.
    collab_yroom_manager = CollabYRoomManager(
        server_app=server_app,
        collab_cm=collab_cm,
    )

    web_app = server_app.web_app
    web_app.settings["collab_file_id_manager"] = collab_fileid_manager
    web_app.settings["collab_yroom_manager"] = collab_yroom_manager

    # Collaboration routes.
    # The frontend constructs:
    #  fileid URL: {baseUrl}/rubin/collab/fileid/index?path={localPath}
    #  room  WS  : {wsUrl}/rubin/collab/collaboration/room/{format}:{type}:{id}
    handlers += [
	(
            rf"{prefix}/collaboration/room/(.*)",
            CollabYRoomWebsocket,
        ),
        (
            rf"{prefix}/fileid/index",
            CollabFileIDIndexHandler,
        ),
    ]
    server_app.log.info("Registered YDoc collaboration routes")

    # Register a graceful-shutdown hook.  When the server stops, we ask the
    # YRoomManager to save all open rooms before the ContentsManager closes.
    _hook_shutdown(server_app, collab_yroom_manager)

def _hook_shutdown(server_app: jupyter_server.serverapp.ServerApp,
                   collab_yroom_manager: YRoomManager) -> None:
    """
    Patch server_app.stop() to call collab_yroom_manager.stop() first.

    This ensures in-flight YDoc changes are persisted before the
    ContentsManager shuts down.  The patch is applied only once; repeated
    calls to _hook_shutdown are idempotent because we check for the marker
    attribute ``_collab_stop_hooked``.
    """

    if getattr(server_app, "_collab_stop_hooked", False):
        return

    orig_stop = getattr(server_app, "stop", None)
    if orig_stop is None or not asyncio.iscoroutinefunction(orig_stop):
        server_app.log.warning(
            "stop() is not async; rooms will not be saved on SIGTERM"
        )
        return

    async def _patched_stop(*args: Any, **kwargs: Any):
        try:
            await collab_yroom_manager.stop()
        except Exception as exc:
            server_app.log.exception("Failed to stop collab yroom_manager")
        return await orig_stop(*args, **kwargs)

    sa = server_app
    # Yes, we are in fact replacing a method.
    sa.stop = _patched_stop  # type: ignore[method-assign, assignment]
    setattr(sa, "_collab_stop_hooked", True)


def _load_jupyter_server_extension(
        server_app: jupyter_server.serverapp.ServerApp
) -> None:
    """Registers the API handler to receive HTTP requests from the frontend
    extension.

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
