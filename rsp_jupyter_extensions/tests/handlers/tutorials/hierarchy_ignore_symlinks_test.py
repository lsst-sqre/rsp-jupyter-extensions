"""Test construction of representation of tree for tutorial notebooks."""

from pathlib import Path
from unittest.mock import ANY

import pytest
import tornado

import rsp_jupyter_extensions.handlers.tutorials as t

from ..._fake import _FakeConnect


def test_ignore_symlinks(
    tutorial_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """We should just skip any symlinks we find, as a cheesy way of not having
    to deal with loops.
    """
    handler = t.TutorialsMenuHandler(
        tornado.web.Application(),
        request=tornado.httputil.HTTPServerRequest(connection=_FakeConnect()),
    )
    sl = Path(tutorial_env / "symlink")
    sl.mkdir()
    this = Path(__file__)
    (sl / "me").symlink_to(this)
    (sl / "here").symlink_to(this.parent)
    (sl / "real_file").write_text("Hello, world!\n")

    assert (sl / "me").is_symlink()
    assert (sl / "here").is_symlink()

    h = handler._build_hierarchy(sl)
    h_p = h.to_primitive()
    assert h_p == {
        "entries": {
            "real_file": {
                "menu_name": "real_file",
                "action": "copy",
                "disposition": "prompt",
                "parent": "/",
                "menu_path": "/real_file",
                "src": ANY,
                "dest": ANY,
            }
        },
        "subhierarchies": None,
    }
