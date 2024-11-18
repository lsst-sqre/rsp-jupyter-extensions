"""Test file copy and retry logic."""

from pathlib import Path

import pytest

from rsp_jupyter_extensions.handlers.tutorials import _copy_and_redir
from rsp_jupyter_extensions.models.tutorials import (
    HierarchyError,
    UserEnvironmentError,
)


def test_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test file copy and retry logic."""
    # Set up environment
    homedir = tmp_path / "home" / "irian"
    homedir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(homedir))
    monkeypatch.setenv("USER", "irian")
    srcdir = tmp_path / "src"
    destdir = homedir / "dest"
    srcdir.mkdir()

    contents = "Hello, world!\n"
    (srcdir / "hello.txt").write_text(contents)

    inp = {
        "action": "copy",
        "disposition": "prompt",
        "parent": None,
        "src": f"{srcdir!s}/hello.txt",
        "dest": f"{destdir!s}/hello.txt",
    }

    outf = destdir / "hello.txt"

    assert not outf.exists()
    assert not outf.parent.exists()

    cr = _copy_and_redir(inp)
    assert cr.status_code == 307
    assert cr.redirect == "/nb/user/irian/lab/tree/dest/hello.txt"
    assert outf.exists()
    assert outf.read_text() == contents

    cr = _copy_and_redir(inp)
    assert cr.status_code == 409
    assert cr.redirect is None

    inp["disposition"] = "abort"

    cr = _copy_and_redir(inp)
    assert cr.status_code == 204
    assert cr.redirect is None

    new_contents = "Greetings, globe!\n"

    (srcdir / "hello.txt").write_text(new_contents)

    inp["disposition"] = "overwrite"

    cr = _copy_and_redir(inp)
    assert cr.status_code == 307
    assert cr.redirect == "/nb/user/irian/lab/tree/dest/hello.txt"
    assert outf.read_text() == new_contents


def test_bad_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test handling of bad inputs and environments."""
    inp = {
        "action": "copy",
        "disposition": "prompt",
        "parent": None,
        "src": "/in/hello.txt",
        "dest": f"{tmp_path}/home/irian/hello.txt",
    }

    monkeypatch.delenv("USER")
    monkeypatch.delenv("HOME")
    with pytest.raises(UserEnvironmentError, match="username"):
        _ = _copy_and_redir(inp)
    monkeypatch.setenv("USER", "irian")
    with pytest.raises(UserEnvironmentError, match="homedir for 'irian'"):
        _ = _copy_and_redir(inp)
    monkeypatch.setenv("HOME", "/nowhere")
    with pytest.raises(
        HierarchyError,
        match="/home/irian/hello.txt' is not contained by '/nowhere'",
    ):
        _ = _copy_and_redir(inp)
