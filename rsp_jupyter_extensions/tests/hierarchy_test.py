"""Test construction of representation of tree for tutorial notebooks."""

from pathlib import Path
from unittest.mock import ANY

import rsp_jupyter_extensions.handlers.tutorials as t


def test_hierarchy(tmp_path: Path) -> None:
    """Test _build_hierarchy(), which underpins the tutorial extension."""

    # Set up test files
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "subsubdir").mkdir()
    for p in (tmp_path, tmp_path / "subdir", tmp_path / "subdir" / "subsubdir"):
        (p / "hello.txt").write_text("Hello, world!\n")
        (p / "hello.py").write_text("print('Hello, world!')\n")

    h1 = t._build_hierarchy(root=tmp_path)
    assert h1 == {
        "hello.py": {
            "action": "copy",
            "dest": ANY,
            "parent": None,
            "src": ANY,
        },
        "hello.txt": {
            "action": "copy",
            "dest": ANY,
            "parent": None,
            "src": ANY,
        },
        "subdir": {
            "hello.py": {
                "action": "copy",
                "dest": ANY,
                "parent": "/subdir",
                "src": ANY,
            },
            "hello.txt": {
                "action": "copy",
                "dest": ANY,
                "parent": "/subdir",
                "src": ANY,
            },
            "subsubdir": {
                "hello.py": {
                    "action": "copy",
                    "dest": ANY,
                    "parent": "/subdir/subsubdir",
                    "src": ANY,
                },
                "hello.txt": {
                    "action": "copy",
                    "dest": ANY,
                    "parent": "/subdir/subsubdir",
                    "src": ANY,
                },
            },
        },
    }

    h2 = t._build_hierarchy(root=tmp_path, suffix=".py")
    assert h2 == {
        "hello": {
            "action": "copy",
            "dest": ANY,
            "parent": None,
            "src": ANY,
        },
        "subdir": {
            "hello": {
                "action": "copy",
                "dest": ANY,
                "parent": "/subdir",
                "src": ANY,
            },
            "subsubdir": {
                "hello": {
                    "action": "copy",
                    "dest": ANY,
                    "parent": "/subdir/subsubdir",
                    "src": ANY,
                },
            },
        },
    }

    h3 = t._build_hierarchy(
        root=tmp_path,
        suffix=".txt",
        action="fetch",
        xform_src=lambda x: "foo",
        xform_dest=lambda x: "bar",
    )
    assert h3 == {
        "hello": {
            "action": "fetch",
            "dest": "bar",
            "parent": None,
            "src": "foo",
        },
        "subdir": {
            "hello": {
                "action": "fetch",
                "dest": "bar",
                "parent": "/subdir",
                "src": "foo",
            },
            "subsubdir": {
                "hello": {
                    "action": "fetch",
                    "dest": "bar",
                    "parent": "/subdir/subsubdir",
                    "src": "foo",
                },
            },
        },
    }
