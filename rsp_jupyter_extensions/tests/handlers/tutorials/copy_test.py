"""Test file copy and retry logic."""

import os
from pathlib import Path

import pytest
import tornado
from pyfakefs.fake_filesystem import FakeFilesystem

from rsp_jupyter_extensions.handlers.tutorials import TutorialsMenuHandler

from ..._fake import _FakeConnect


@pytest.mark.asyncio
async def test_copy(rsp_fs: FakeFilesystem) -> None:
    """Test file copy and retry logic."""
    # Set up environment
    tmp_path = Path(os.environ.get("TMPDIR", "/tmp"))
    srcdir = tmp_path / "src"
    destdir = Path(os.environ["HOME"]) / "dest"
    srcdir.mkdir()

    contents = "Hello, world!\n"
    (srcdir / "hello.txt").write_text(contents)

    inp = {
        "menu_name": "hello.txt",
        "action": "copy",
        "disposition": "prompt",
        "parent": "/",
        "menu_path": "/hello.txt",
        "src": f"{srcdir!s}/hello.txt",
        "dest": f"{destdir!s}/hello.txt",
    }

    outf = destdir / "hello.txt"

    assert not outf.exists()
    assert not outf.parent.exists()

    handler = TutorialsMenuHandler(
        tornado.web.Application(),
        request=tornado.httputil.HTTPServerRequest(connection=_FakeConnect()),
    )

    cr = await handler._copy_and_guide(inp)
    assert cr.status_code == 200
    assert cr.dest == "dest/hello.txt"
    assert outf.exists()
    assert outf.read_text() == contents

    cr = await handler._copy_and_guide(inp)
    assert cr.status_code == 409
    assert cr.dest is None

    inp["disposition"] = "abort"

    cr = await handler._copy_and_guide(inp)
    assert cr.status_code == 204
    assert cr.dest is None

    new_contents = "Greetings, globe!\n"

    (srcdir / "hello.txt").write_text(new_contents)

    inp["disposition"] = "overwrite"

    cr = await handler._copy_and_guide(inp)
    assert cr.status_code == 200
    assert cr.dest == "dest/hello.txt"
    assert outf.read_text() == new_contents
