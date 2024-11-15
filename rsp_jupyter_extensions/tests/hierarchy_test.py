"""Test construction of representation of tree for tutorial notebooks."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import ANY

import pytest

import rsp_jupyter_extensions.handlers.tutorials as t
from rsp_jupyter_extensions.models.tutorials import (
    Actions,
    Hierarchy,
    HierarchyEntry,
    HierarchyError,
)


def test_basic_hierarchy(tmp_path: Path) -> None:
    """Test _build_hierarchy(), which underpins the tutorial extension.

    Create three different views of the same filesystem, and roundtrip each
    one through serialization and back.
    """
    # Set up test files
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "subsubdir").mkdir()
    for p in (
        tmp_path,
        tmp_path / "subdir",
        tmp_path / "subdir" / "subsubdir",
    ):
        (p / "hello.txt").write_text("Hello, world!\n")
        (p / "hello.py").write_text("print('Hello, world!')\n")

    h1 = t._build_hierarchy(root=tmp_path)
    h1_p = h1.to_primitive()
    assert h1_p == {
        "entries": {
            "hello.py": {
                "action": "copy",
                "disposition": "prompt",
                "parent": None,
                "src": ANY,
                "dest": ANY,
            },
            "hello.txt": {
                "action": "copy",
                "disposition": "prompt",
                "parent": None,
                "src": ANY,
                "dest": ANY,
            },
        },
        "subhierarchies": {
            "subdir": {
                "entries": {
                    "hello.py": {
                        "action": "copy",
                        "disposition": "prompt",
                        "parent": "/subdir",
                        "src": ANY,
                        "dest": ANY,
                    },
                    "hello.txt": {
                        "action": "copy",
                        "disposition": "prompt",
                        "parent": "/subdir",
                        "src": ANY,
                        "dest": ANY,
                    },
                },
                "subhierarchies": {
                    "subsubdir": {
                        "entries": {
                            "hello.py": {
                                "action": "copy",
                                "disposition": "prompt",
                                "parent": "/subdir/subsubdir",
                                "src": ANY,
                                "dest": ANY,
                            },
                            "hello.txt": {
                                "action": "copy",
                                "disposition": "prompt",
                                "parent": "/subdir/subsubdir",
                                "src": ANY,
                                "dest": ANY,
                            },
                        },
                        "subhierarchies": None,
                    }
                },
            }
        },
    }
    h1_a = Hierarchy.from_primitive(h1_p)
    assert h1 == h1_a

    h2 = t._build_hierarchy(root=tmp_path, suffix=".py")
    h2_p = h2.to_primitive()

    assert h2_p == {
        "entries": {
            "hello": {
                "action": "copy",
                "disposition": "prompt",
                "parent": None,
                "src": ANY,
                "dest": ANY,
            }
        },
        "subhierarchies": {
            "subdir": {
                "entries": {
                    "hello": {
                        "action": "copy",
                        "disposition": "prompt",
                        "parent": "/subdir",
                        "src": ANY,
                        "dest": ANY,
                    }
                },
                "subhierarchies": {
                    "subsubdir": {
                        "entries": {
                            "hello": {
                                "action": "copy",
                                "disposition": "prompt",
                                "parent": "/subdir/subsubdir",
                                "src": ANY,
                                "dest": ANY,
                            }
                        },
                        "subhierarchies": None,
                    }
                },
            }
        },
    }
    h2_a = Hierarchy.from_primitive(h2_p)
    assert h2 == h2_a

    h3 = t._build_hierarchy(
        root=tmp_path,
        suffix=".txt",
        action=Actions.FETCH,
        xform_src=lambda x: f"https://example.com/foo/{Path(Path(x).name)}",
        xform_dest=lambda x: Path("bar"),
    )
    h3_p = h3.to_primitive()

    assert h3_p == {
        "entries": {
            "hello": {
                "action": "fetch",
                "disposition": "prompt",
                "parent": None,
                "src": "https://example.com/foo/hello.txt",
                "dest": "bar",
            }
        },
        "subhierarchies": {
            "subdir": {
                "entries": {
                    "hello": {
                        "action": "fetch",
                        "disposition": "prompt",
                        "parent": "/subdir",
                        "src": "https://example.com/foo/hello.txt",
                        "dest": "bar",
                    }
                },
                "subhierarchies": {
                    "subsubdir": {
                        "entries": {
                            "hello": {
                                "action": "fetch",
                                "disposition": "prompt",
                                "parent": "/subdir/subsubdir",
                                "src": "https://example.com/foo/hello.txt",
                                "dest": "bar",
                            }
                        },
                        "subhierarchies": None,
                    }
                },
            }
        },
    }

    h3_a = Hierarchy.from_primitive(h3_p)
    assert h3 == h3_a


def test_ignore_symlinks(tmp_path: Path) -> None:
    """We should just skip any symlinks we find, as a cheesy way of not having
    to deal with loops.
    """
    os.symlink(__file__, tmp_path / "me")
    os.symlink(Path(__file__).parent, tmp_path / "here")
    (tmp_path / "real_file").write_text("Hello, world!\n")

    assert (tmp_path / "me").is_symlink()
    assert (tmp_path / "here").is_symlink()

    h = t._build_hierarchy(tmp_path)
    h_p = h.to_primitive()
    assert h_p == {
        "entries": {
            "real_file": {
                "action": "copy",
                "disposition": "prompt",
                "parent": None,
                "src": ANY,
                "dest": ANY,
            }
        },
        "subhierarchies": None,
    }


def test_bad_construction() -> None:
    """Demonstrate that Hierarchy construction fails as it should."""

    @dataclass
    class TestInput:
        """Convenience class for constructor testing."""

        name: str
        value: dict[str, Any]
        match: str

    inp = [
        TestInput(name="missing_toplevel", value={}, match=""),
        TestInput(
            name="extra_fields",
            value={
                "entries": None,
                "subhierarchies": None,
                "extra_field": True,
            },
            match="Unknown fields",
        ),
        TestInput(
            name="malformed_entry",
            value={
                "entries": {"foo": "bar"},
                "subhierarchies": None,
            },
            match="not a dict",
        ),
    ]

    for tst in inp:
        with pytest.raises(HierarchyError, match=tst.match):
            _ = Hierarchy.from_primitive(tst.value)

    inp = [
        TestInput(name="missing_toplevel", value={}, match=""),
        TestInput(
            name="malformed_entry",
            value={
                "action": 4,
            },
            match="not a string",
        ),
        TestInput(
            name="malformed_parent_entry",
            value={
                "action": "a",
                "disposition": "b",
                "src": "c",
                "dest": "d",
                "parent": 4,
            },
            match="neither a string",
        ),
        TestInput(
            name="extra_fields",
            value={
                "action": "a",
                "disposition": "b",
                "src": "c",
                "dest": "d",
                "parent": None,
                "extra_field": True,
            },
            match="Unknown keys",
        ),
        TestInput(
            name="bad_action",
            value={
                "action": "a",
                "disposition": "b",
                "src": "c",
                "dest": "d",
                "parent": None,
            },
            match=r"'action'=(.*): not in",
        ),
        TestInput(
            name="bad_disposition",
            value={
                "action": "copy",
                "disposition": "b",
                "src": "c",
                "dest": "d",
                "parent": None,
            },
            match=r"'disposition'=(.*): not in",
        ),
    ]

    for tst in inp:
        with pytest.raises(HierarchyError, match=tst.match):
            _ = HierarchyEntry.from_primitive(tst.value)
