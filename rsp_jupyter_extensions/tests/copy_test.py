"""Test file copy and retry logic."""

import os
from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from rsp_jupyter_extensions.handlers.tutorials import _copy_and_guide
from rsp_jupyter_extensions.models.tutorials import (
    HierarchyError,
    UserEnvironmentError,
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

    monkeypatch.delenv("HOME")
    with pytest.raises(
        UserEnvironmentError, match="home directory is not set"
    ):
        _ = _copy_and_guide(inp)
    monkeypatch.setenv("HOME", "/nowhere")
    with pytest.raises(
        HierarchyError,
        match="/hello.txt' is not contained by '/nowhere'",
    ):
        _ = _copy_and_guide(inp)
