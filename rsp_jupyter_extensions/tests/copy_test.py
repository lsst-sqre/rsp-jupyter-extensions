"""Test file copy and retry logic."""

import os
from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from rsp_jupyter_extensions.handlers.tutorials import _copy_and_guide
from rsp_jupyter_extensions.models.tutorials import (
    HierarchyError,
)


def test_copy(rsp_fs: FakeFilesystem) -> None:
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

    cr = _copy_and_guide(inp)
    assert cr.status_code == 200
    assert cr.dest == "dest/hello.txt"
    assert outf.exists()
    assert outf.read_text() == contents

    cr = _copy_and_guide(inp)
    assert cr.status_code == 409
    assert cr.dest is None

    inp["disposition"] = "abort"

    cr = _copy_and_guide(inp)
    assert cr.status_code == 204
    assert cr.dest is None

    new_contents = "Greetings, globe!\n"

    (srcdir / "hello.txt").write_text(new_contents)

    inp["disposition"] = "overwrite"

    cr = _copy_and_guide(inp)
    assert cr.status_code == 200
    assert cr.dest == "dest/hello.txt"
    assert outf.read_text() == new_contents


def test_alternate_root(
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
    monkeypatch.setenv("FILEBROWSER_ROOT", "root")
    cr = _copy_and_guide(inp)
    assert not Path("/dest/hello.txt").exists()
    assert Path("/home/irian/dest/hello.txt").read_text() == txt
    assert cr.status_code == 200
    assert cr.dest == "home/irian/dest/hello.txt"


def test_bad_copy(
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

    with pytest.raises(
        HierarchyError,
        match="/hello.txt' is not contained by '/home/irian'",
    ):
        _ = _copy_and_guide(inp)
