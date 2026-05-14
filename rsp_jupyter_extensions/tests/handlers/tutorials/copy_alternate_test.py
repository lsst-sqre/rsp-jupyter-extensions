"""Test file copy and retry logic."""

from pathlib import Path

import pytest
import tornado
from pyfakefs.fake_filesystem import FakeFilesystem

from rsp_jupyter_extensions.handlers.tutorials import TutorialsMenuHandler

from ..._fake import _FakeConnect


@pytest.mark.asyncio
async def test_alternate_root(
    rsp_fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test alternate root dir."""
    inp = {
        "menu_name": "hello.txt",
        "action": "copy",
        "disposition": "prompt",
        "parent": "/",
        "menu_path": "/hello.txt",
        "src": "/in/hello.txt",
        "dest": "dest/hello.txt",
    }

    txt = "Howdy, Prime Material Plane!\n"
    Path("/in").mkdir()
    Path("/home/irian/dest").mkdir(parents=True)
    Path("/in/hello.txt").write_text(txt)
    handler = TutorialsMenuHandler(
        tornado.web.Application(),
        request=tornado.httputil.HTTPServerRequest(connection=_FakeConnect()),
    )
    handler.settings["rsp_config"].file_browser_root = "root"
    handler.settings[
        "rsp_config"
    ].home_relative_to_file_browser_root = "home/irian"

    cr = await handler._copy_and_guide(inp)
    assert not Path("/dest/hello.txt").exists()
    assert Path("/home/irian/dest/hello.txt").read_text() == txt
    assert cr.status_code == 200
    assert cr.dest == "home/irian/dest/hello.txt"
    # Tornado, and its settings, are persistent.
    # Thus, we need to rebuild the config with the original settings.
    handler.settings["rsp_config"].file_browser_root = "home"
    handler.settings["rsp_config"].home_relative_to_file_browser_root = ""
