"""Test construction of representation of tree for tutorial notebooks."""

from pathlib import Path
from unittest.mock import ANY

from rsp_jupyter_extensions.models.tutorials import Actions
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
            "disposition": "prompt",
            "parent": None,
            "src": ANY,
        },
        "hello.txt": {
            "action": "copy",
            "dest": ANY,
            "disposition": "prompt",
            "parent": None,
            "src": ANY,
        },
        "subdir": {
            "hello.py": {
                "action": "copy",
                "dest": ANY,
                "disposition": "prompt",
                "parent": "/subdir",
                "src": ANY,
            },
            "hello.txt": {
                "action": "copy",
                "dest": ANY,
                "disposition": "prompt",
                "parent": "/subdir",
                "src": ANY,
            },
            "subsubdir": {
                "hello.py": {
                    "action": "copy",
                    "dest": ANY,
                    "disposition": "prompt",
                    "parent": "/subdir/subsubdir",
                    "src": ANY,
                },
                "hello.txt": {
                    "action": "copy",
                    "dest": ANY,
                    "disposition": "prompt",
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
            "disposition": "prompt",
            "parent": None,
            "src": ANY,
        },
        "subdir": {
            "hello": {
                "action": "copy",
                "dest": ANY,
                "disposition": "prompt",
                "parent": "/subdir",
                "src": ANY,
            },
            "subsubdir": {
                "hello": {
                    "action": "copy",
                    "dest": ANY,
                    "disposition": "prompt",
                    "parent": "/subdir/subsubdir",
                    "src": ANY,
                },
            },
        },
    }

    h3 = t._build_hierarchy(
        root=tmp_path,
        suffix=".txt",
        action=Actions.FETCH,
        xform_src=lambda x: f"https://example.com/foo/{Path(Path(x).name)}",
        xform_dest=lambda x: Path("bar"),
    )
    assert h3 == {
        "hello": {
            "action": "fetch",
            "dest": "bar",
            "disposition": "prompt",
            "parent": None,
            "src": "https://example.com/foo/hello.txt",
        },
        "subdir": {
            "hello": {
                "action": "fetch",
                "dest": "bar",
                "disposition": "prompt",
                "parent": "/subdir",
                "src": "https://example.com/foo/hello.txt",
            },
            "subsubdir": {
                "hello": {
                    "action": "fetch",
                    "dest": "bar",
                    "disposition": "prompt",
                    "parent": "/subdir/subsubdir",
                    "src": "https://example.com/foo/hello.txt",
                },
            },
        },
    }
