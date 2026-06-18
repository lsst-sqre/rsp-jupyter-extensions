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
that jupyter-server-documents does.
"""

from pathlib import Path
from typing import cast

import jupyter_server
from jupyter_events import EventLogger
from jupyter_server.base.handlers import APIHandler
from jupyter_server.services.contents.handlers import (
    CheckpointsHandler,
    ContentsHandler,
    ModifyCheckpointsHandler,
    TrustNotebooksHandler,
)
from jupyter_server.services.contents.manager import ContentsManager
from jupyter_server_documents.handlers import FileIDIndexHandler
from jupyter_server_documents.outputs import OutputsManager
from jupyter_server_documents.rooms.yroom_manager import YRoomManager
from jupyter_server_documents.websockets import YRoomWebsocket
from jupyter_server_fileid.manager import LocalFileIdManager

from .config_generator import ConfigGenerator

COLLAB_SETTINGS_KEY = "collab_contents_manager"

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


def build_collab_ydoc_classes() -> dict[str, type] | None:
    """Build YDoc handler/manager classes for COLLAB_DIR.

    Returns
    -------
    dict[str, class] | None
        Mapping between class name and class itself for the YRoom subclass
        implementation, or None if COLLAB_DIR doesn't exist or is not a
        directory.

    Notes
    -----
    This requires both ``jupyter_server_documents`` and
    ``jupyter_server_fileid``.  Both of these are in the RSP already.
    """
    if COLLAB_DIR is None:
        return None

    # ------------------------------------------------------------------
    # CollabFileIDIndexHandler
    # ------------------------------------------------------------------

    class CollabFileIDIndexHandler(FileIDIndexHandler):
        """
        Serves ``POST .../fileid/index``.

        Redirects the ``file_id_manager`` property to the collab-scoped
        LocalFileIdManager so that file IDs issued for collab files are
        tracked against the collab root, not $HOME.
        """

        @property
        def file_id_manager(self) -> LocalFileIdManager:
            return cast(
                "LocalFileIdManager", self.settings["collab_file_id_manager"]
            )

    # ------------------------------------------------------------------
    # CollabYRoomManager
    # ------------------------------------------------------------------

    class CollabYRoomManager(YRoomManager):
        """
        YRoomManager for collab files.

        Initialised with ``parent=None`` (no config inheritance from a
        ServerDocsApp) and direct references to the collab contents manager
        and file-ID manager.

        The base-class ``__init__`` starts the auto-free background task via
        ``asyncio.get_event_loop().create_task()``.  The caller must ensure
        the event loop is already running at instantiation time, which is
        guaranteed because ``_load_jupyter_server_extension`` is invoked from
        within Jupyter Server's async startup sequence.
        """

        def __init__(
            self,
            *,
            server_app: jupyter_server.serverapp.ServerApp,
            collab_cm: ContentsManager,
        ) -> None:
            super().__init__(parent=None)  # starts _auto_free_rooms_task
            self._server_app = server_app
            self._collab_cm = collab_cm
            self.log = server_app.log  # propagate logs to server logger

        @property
        def contents_manager(self) -> ContentsManager:
            return self._collab_cm

        @property
        def fileid_manager(self) -> LocalFileIdManager:
            """
            Returns the collab-scoped LocalFileIdManager stored in
            web_app.settings by _load_jupyter_server_extension().
            """
            # Settings is a map of str to Any.
            return cast(
                "LocalFileIdManager",
                self._server_app.web_app.settings["collab_file_id_manager"],
            )

        @property
        def event_logger(self) -> EventLogger | None:
            return self._server_app.event_logger

        @property
        def outputs_manager(self) -> OutputsManager:
            """
            Reuse the OutputsManager registered by ServerDocsApp (stored at
            settings["outputs_manager"]).  Returns None if not present; in
            that case YRoomFileAPI skips notebook-output processing.
            """
            return cast(
                "OutputsManager",
                self._server_app.web_app.settings.get("outputs_manager"),
            )

    # ------------------------------------------------------------------
    # CollabYRoomWebsocket
    # ------------------------------------------------------------------

    class CollabYRoomWebsocket(YRoomWebsocket):
        """
        WebSocket handler for ``.../collaboration/room/<room_id>``.

        Overrides the three Tornado-settings lookups so that this handler
        drives the collab YRoomManager, file-ID manager, and contents
        manager completely independently of the default $HOME stack.
        """

        @property
        def yroom_manager(self) -> YRoomManager:
            return cast("YRoomManager", self.settings["collab_yroom_manager"])

        @property
        def fileid_manager(self) -> LocalFileIdManager:
            return cast(
                "LocalFileIdManager", self.settings["collab_file_id_manager"]
            )

        @property
        def contents_manager(self) -> ContentsManager:
            return cast(
                "ContentsManager", self.settings["collab_contents_manager"]
            )

    return {
        "CollabFileIDIndexHandler": CollabFileIDIndexHandler,
        "CollabYRoomManager": CollabYRoomManager,
        "CollabYRoomWebsocket": CollabYRoomWebsocket,
        "LocalFileIdManager": LocalFileIdManager,
    }
