"""Register handlers for RSP extension routes."""

import asyncio
import logging
import os
from functools import partial
from pathlib import Path
from typing import Any

import jupyter_server
import jupyterlab
from jupyter_core.paths import jupyter_data_dir
from jupyter_events.schema_registry import SchemaRegistryException
from jupyter_server.services.contents.filemanager import (
    AsyncFileContentsManager,
    ContentsManager,
)
from jupyter_server.utils import url_path_join as ujoin
from jupyter_server_ydoc.utils import (
    AWARENESS_EVENTS_SCHEMA_PATH,
    EVENTS_SCHEMA_PATH,
    FORK_EVENTS_SCHEMA_PATH,
)

from .handlers.abnormal import AbnormalStartupHandler
from .handlers.collab_filebrowser import (
    COLLAB_FILE_ID_MANAGER_KEY,
    COLLAB_SETTINGS_KEY,
    CollabCheckpointsHandler,
    CollabContentsHandler,
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
        if ydoc_classes is not None:
            _register_collab_ydoc(
                server_app = server_app,
                collab_cm = cm,
                prefix = ujoin(base_url, "/rubin/collab"),
                host_pattern = host_pattern,
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


def _register_collab_ydoc(
    *,
    server_app: jupyter_server.serverapp.ServerApp,
    collab_cm: ContentsManager,
    prefix: str,
    host_pattern: str,
    ydoc_classes: dict[str, Any],
    collab_dir: str
) -> None:
    """Instantiate and register all collab YDoc collaboration objects.

    Builds a ``jupyter_server_ydoc`` (jupyter-collaboration) real-time
    collaboration stack scoped entirely to ``collab_dir``: its own file-ID
    manager, websocket server, file-loader mapping, and YStore database, all
    independent of the default ``$HOME`` collaboration stack.  The room
    websocket and file-ID index routes are registered with the web app.
    """
    LocalFileIdManager = ydoc_classes["LocalFileIdManager"]
    JupyterWebsocketServer = ydoc_classes["JupyterWebsocketServer"]
    FileLoaderMapping = ydoc_classes["FileLoaderMapping"]
    SQLiteYStore = ydoc_classes["SQLiteYStore"]
    exception_logger = ydoc_classes["exception_logger"]
    CollabYDocWebSocketHandler = ydoc_classes["CollabYDocWebSocketHandler"]
    CollabFileIDIndexHandler = ydoc_classes["CollabFileIDIndexHandler"]

    data_dir = Path(jupyter_data_dir())

    # File-ID manager: isolated SQLite database, root = collab only.
    # Keeping the root there prevents the database from escaping into
    # the wider filesystem (for instance, /rubin can easily have millions to
    # billions of files).
    collab_fileid_manager = LocalFileIdManager(
        root_dir=collab_dir,
        db_path=str(data_dir / "collab_file_ids.db"),
    )
    collab_fileid_manager.log = server_app.log

    # YStore class: a single SQLite database, dedicated to the collab stack,
    # holding the Y update history for every collab document.  The base
    # YDocWebSocketHandler instantiates it per-document as
    # ``ystore_class(path=..., log=...)``, so we bind the db_path here.
    ystore_class = partial(
        SQLiteYStore, db_path=str(data_dir / "collab_ystore.db")
    )

    # Websocket server: communicates document updates to all clients in a room.
    collab_ws_server = JupyterWebsocketServer(
        ystore_class=ystore_class,
        rooms_ready=False,
        auto_clean_rooms=False,
        exception_handler=exception_logger,
        log=server_app.log,
    )

    # File-loader mapping: maps rooms to file loaders that read/write through
    # the collab contents manager.  FileLoaderMapping reads only
    # ``contents_manager`` and ``file_id_manager`` from the settings dict it is
    # handed, so we give it a private dict wired to the collab stack rather
    # than the global ``web_app.settings`` (which points at ``$HOME``).
    collab_loader_settings = {
        "contents_manager": collab_cm,
        "file_id_manager": collab_fileid_manager,
    }
    collab_file_loaders = FileLoaderMapping(
        collab_loader_settings,
        server_app.log,
        file_poll_interval=1.0,
    )

    web_app = server_app.web_app
    web_app.settings[COLLAB_FILE_ID_MANAGER_KEY] = collab_fileid_manager

    # Register the collaboration event schemas defensively.  These are
    # normally registered by the jupyter_server_ydoc server extension, but we
    # do not rely on that extension being enabled; emitting on an unregistered
    # schema is a silent no-op, and re-registering an already-registered schema
    # raises, so we guard against both.
    event_logger = server_app.event_logger
    if event_logger is not None:
        for schema_path in (
            EVENTS_SCHEMA_PATH,
            AWARENESS_EVENTS_SCHEMA_PATH,
            FORK_EVENTS_SCHEMA_PATH,
        ):
            try:
                event_logger.register_event_schema(schema_path)
            except SchemaRegistryException:
                pass

    # Collaboration routes.
    # The frontend constructs:
    #  fileid URL: {baseUrl}/rubin/collab/fileid/index?path={localPath}
    #  room  WS  : {wsUrl}/rubin/collab/collaboration/room/{format}:{type}:{id}
    room_locks: dict[str, asyncio.Lock] = {}
    handlers: list[tuple] = [
        (
            rf"{prefix}/collaboration/room/(.*)",
            CollabYDocWebSocketHandler,
            {
                "ywebsocket_server": collab_ws_server,
                "file_loaders": collab_file_loaders,
                "ystore_class": ystore_class,
                "room_locks": room_locks,
            },
        ),
        (
            rf"{prefix}/fileid/index",
            CollabFileIDIndexHandler,
        ),
    ]
    web_app.add_handlers(host_pattern, handlers)
    server_app.log.info("Registered YDoc collaboration routes")

    # Register a graceful-shutdown hook.  When the server stops, we clean up
    # the websocket server (which persists in-flight YDoc changes) and the
    # file loaders before the ContentsManager shuts down.
    _hook_shutdown(server_app, collab_ws_server, collab_file_loaders)

def _hook_shutdown(server_app: jupyter_server.serverapp.ServerApp,
                   collab_ws_server: Any,
                   collab_file_loaders: Any) -> None:
    """
    Patch server_app.stop() to clean up the collab collaboration stack first.

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
            await collab_ws_server.clean()
        except Exception:
            server_app.log.exception("Failed to clean collab websocket server")
        try:
            await collab_file_loaders.clear()
        except Exception:
            server_app.log.exception("Failed to clear collab file loaders")
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
