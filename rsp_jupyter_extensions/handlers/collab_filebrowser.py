"""Server-side handlers exposing a second contents API rooted at wherever
$NUBLADO_COLLAB_DIR points.

This mirrors the standard `/api/contents/...` route tree at
`/rubin/collab/...`, backed by a dedicated ContentsManager whose `root_dir` is
`$NUBLADO_COLLAB_DIR`. The labextension registers a `Drive` named `collab`
that talks to this endpoint.
"""

from typing import Any

from jupyter_server.base.handlers import APIHandler
from jupyter_server.services.contents.handlers import (
    CheckpointsHandler,
    ContentsHandler,
    ModifyCheckpointsHandler,
    TrustNotebooksHandler,
)

COLLAB_SETTINGS_KEY = "collab_contents_manager"


class _CollabContentsMixin(APIHandler):
    """Override `contents_manager` to read the collab manager from settings."""

    @property
    def contents_manager(self) -> Any:
        return self.settings[COLLAB_SETTINGS_KEY]


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
