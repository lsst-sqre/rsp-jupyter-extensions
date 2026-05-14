"""Test file copy and retry logic."""

import os
import re
from pathlib import Path

import pytest
import tornado
from pyfakefs.fake_filesystem import FakeFilesystem

from rsp_jupyter_extensions.exceptions import (
    HierarchyError,
)
from rsp_jupyter_extensions.handlers.tutorials import TutorialsMenuHandler

from ..._fake import _FakeConnect


@pytest.mark.asyncio
async def test_bad_copy(
    rsp_fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test handling of bad inputs and environments."""
    tmp_path = Path(os.environ.get("TMPDIR", "/tmp"))
    inp = {
        "menu_name": "hello.txt",
        "action": "copy",
        "disposition": "prompt",
        "parent": "/",
        "menu_path": "/hello.txt",
        "src": "/in/hello.txt",
        "dest": f"{tmp_path}/hello.txt",
    }

    Path("/in").mkdir()
    Path("/in/hello.txt").write_text("Howdy, Prime Material Plane!\n")

    handler = TutorialsMenuHandler(
        tornado.web.Application(),
        request=tornado.httputil.HTTPServerRequest(connection=_FakeConnect()),
    )
    with pytest.raises(
        HierarchyError,
        match=re.escape("/hello.txt' is not contained by '/home/irian'"),
    ):
        _ = await handler._copy_and_guide(inp)
