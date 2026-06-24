"""Server-side handlers exposing a second contents API rooted at
wherever our config's collab_dir points.

This mirrors the standard `/api/contents/...` route tree at
`/rubin/collab/...`, backed by a dedicated ContentsManager whose
`root_dir` is current `$NUBLADO_COLLAB_DIR`. (In future, the
configration manager will not rely on environment variables to
determine this.)

The labextension registers a `Drive` named `collab` that talks to this
endpoint.  There's also a little trickiness on the front end about
swapping in YDoc-aware classes that point at the correct extension
endpoint.

That's not all, unfortunately.  That gets us a standard
ContentsManager API.  That is insufficient for the real-time
collaboration features, which is the entire point of the collaboration
directory.

Thus we also need to build new classes that do all the YDoc handling
that jupyter-collaboration (the ``jupyter_server_ydoc`` machinery) does,
but scoped to the collab directory rather than ``$HOME``.
"""

from pathlib import Path
from typing import Any, cast

from jupyter_server.auth.decorator import authorized
from jupyter_server.base.handlers import APIHandler
from jupyter_server.services.contents.handlers import (
    CheckpointsHandler,
    ContentsHandler,
    ModifyCheckpointsHandler,
    TrustNotebooksHandler,
)
from jupyter_server.services.contents.manager import ContentsManager
from jupyter_server_fileid.manager import BaseFileIdManager, LocalFileIdManager
from jupyter_server_ydoc.handlers import YDocWebSocketHandler
from jupyter_server_ydoc.loaders import FileLoaderMapping
from jupyter_server_ydoc.stores import SQLiteYStore
from jupyter_server_ydoc.utils import SERVER_SESSION
from jupyter_server_ydoc.websocketserver import (
    JupyterWebsocketServer,
    exception_logger,
)
from tornado import web
from tornado.escape import json_encode

from .config_generator import ConfigGenerator

COLLAB_SETTINGS_KEY = "collab_contents_manager"
# web_app.settings key holding the collab-scoped LocalFileIdManager.
COLLAB_FILE_ID_MANAGER_KEY = "collab_file_id_manager"

# Retrieve collaboration directory, if set.
_cfggen = ConfigGenerator()
_cfg = _cfggen.generate_config()

# Ensure that COLLAB_DIR points to a valid directory
COLLAB_DIR = _cfg.collab_dir
COLLAB_PATH: Path | None = None
if COLLAB_DIR:
    COLLAB_PATH = Path(COLLAB_DIR)
    if not COLLAB_PATH.is_dir():
        COLLAB_DIR = None
        COLLAB_PATH = None


class _CollabContentsMixin(APIHandler):
    """Override `contents_manager` to read the collab manager from settings."""

    @property
    def contents_manager(self) -> ContentsManager:
        return cast("ContentsManager", self.settings[COLLAB_SETTINGS_KEY])


class CollabContentsHandler(_CollabContentsMixin, ContentsHandler):
    """ContentsHandler for collab directory."""


class CollabCheckpointsHandler(_CollabContentsMixin, CheckpointsHandler):
    """CheckpointsHandler for collab directory."""


class CollabModifyCheckpointsHandler(
    _CollabContentsMixin, ModifyCheckpointsHandler
):
    """ModifyCheckpointsHandler for collab directory."""


class CollabTrustNotebooksHandler(_CollabContentsMixin, TrustNotebooksHandler):
    """TrustNotebooksHandler for collab directory."""


### YDoc collaboration


def build_collab_ydoc_classes() -> dict[str, Any] | None:
    """Build YDoc handler/manager classes for COLLAB_DIR.

    Returns
    -------
    dict[str, Any] | None
        Mapping between symbol name and the class (or callable) itself for
        the ``jupyter_server_ydoc`` collaboration implementation, or None if
        COLLAB_DIR doesn't exist or is not a directory.  The collab-scoped
        handler classes are built dynamically here; the remaining
        ``jupyter_server_ydoc`` building blocks are passed through so that all
        wiring (and the choice of collaboration backend) stays localized.

    Notes
    -----
    This requires both ``jupyter_server_ydoc`` (shipped as part of
    ``jupyter-collaboration``) and ``jupyter_server_fileid``.  Both of
    these are in the RSP already.
    """
    if COLLAB_DIR is None:
        return None

    # ------------------------------------------------------------------
    # CollabFileIDIndexHandler
    # ------------------------------------------------------------------

    class CollabFileIDIndexHandler(APIHandler):
        """
        Serves ``POST .../fileid/index``.

        Reimplements the trivial file-ID index endpoint (which lives in
        neither jupyter_server nor jupyter_server_ydoc proper) against the
        collab-scoped LocalFileIdManager, so that file IDs issued for collab
        files are tracked against the collab root, not ``$HOME``.

        The response shape ``{"id": ..., "path": ...}`` matches what the
        front end (``collab_browser.ts``) expects.
        """

        auth_resource = "contents"

        @property
        def file_id_manager(self) -> BaseFileIdManager:
            return cast(
                "BaseFileIdManager",
                self.settings[COLLAB_FILE_ID_MANAGER_KEY],
            )

        @web.authenticated
        @authorized
        def post(self) -> None:
            try:
                path = self.get_argument("path")
            except web.MissingArgumentError:
                raise web.HTTPError(
                    400,
                    log_message=(
                        "'path' parameter was not provided in the request."
                    ),
                ) from None
            file_id = self.file_id_manager.index(path)
            self.write(json_encode({"id": file_id, "path": path}))

    # ------------------------------------------------------------------
    # CollabYDocWebSocketHandler
    # ------------------------------------------------------------------

    class CollabYDocWebSocketHandler(YDocWebSocketHandler):
        """
        WebSocket handler for ``.../collaboration/room/<room_id>``.

        Subclasses the stock ``jupyter_server_ydoc`` handler.  The collab
        websocket server, file-loader mapping, YStore class, and room locks
        are all injected via the Tornado route's ``initialize`` kwargs (see
        ``_register_collab_ydoc`` in the package ``__init__``), so this
        handler drives a collab-scoped stack that is fully independent of the
        default ``$HOME`` real-time-collaboration stack.

        Two seams are overridden:

        * ``initialize`` repoints the handler's ``file_id_manager`` at the
          collab-scoped manager.  The base class reads
          ``self.settings["file_id_manager"]`` (the ``$HOME`` manager); the
          only place it is used directly is event emission (``_emit``), and we
          want those paths resolved against the collab root.

        * ``get_query_argument`` spoofs the ``sessionId`` query argument.  The
          base ``open()`` gates reconnections on a ``sessionId`` handshake used
          by the official jupyter-docprovider front end and closes any client
          that does not negotiate one (close code 1003, ``reloadable=True``).
          The RSP front end connects with a plain ``y-websocket`` provider that
          sends no ``sessionId``, so we report the current server session and
          let the base handler skip the reload-gating branch entirely.
        """

        def initialize(self, *args: Any, **kwargs: Any) -> None:
            super().initialize(*args, **kwargs)
            self._file_id_manager = self.settings[COLLAB_FILE_ID_MANAGER_KEY]

        def get_query_argument(  # type: ignore[override]
            self, name: str, *args: Any, **kwargs: Any
        ) -> Any:
            if name == "sessionId":
                return SERVER_SESSION
            return super().get_query_argument(name, *args, **kwargs)

    return {
        "CollabFileIDIndexHandler": CollabFileIDIndexHandler,
        "CollabYDocWebSocketHandler": CollabYDocWebSocketHandler,
        "FileLoaderMapping": FileLoaderMapping,
        "JupyterWebsocketServer": JupyterWebsocketServer,
        "SQLiteYStore": SQLiteYStore,
        "LocalFileIdManager": LocalFileIdManager,
        "exception_logger": exception_logger,
    }
