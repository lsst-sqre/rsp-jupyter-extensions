"""Test construction of representation of tree for tutorial notebooks."""

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import ANY

import pytest
import tornado

import rsp_jupyter_extensions.handlers.tutorials as t
from rsp_jupyter_extensions.models.tutorials import (
    Actions,
    Hierarchy,
    HierarchyEntry,
    HierarchyError,
)


class _FakeConnect(tornado.httputil.HTTPConnection):
    def set_close_callback(self, arg: Any) -> None:
        pass


HDLR = t.TutorialsMenuHandler(
    tornado.web.Application(),
    request=tornado.httputil.HTTPServerRequest(connection=_FakeConnect()),
)


def test_basic_hierarchy(tutorial_env: Path) -> None:
    """Test _build_hierarchy(), which underpins the tutorial extension.

    Create three different views of the same filesystem, and roundtrip each
    one through serialization and back.
    """
    h1 = HDLR._build_hierarchy(root=tutorial_env)
    h1_p = h1.to_primitive()
    assert h1_p == {
        "entries": {
            "hello.py": {
                "menu_name": "hello.py",
                "action": "copy",
                "disposition": "prompt",
                "parent": "/",
                "menu_path": "/hello.py",
                "src": ANY,
                "dest": ANY,
            },
            "hello.txt": {
                "menu_name": "hello.txt",
                "action": "copy",
                "disposition": "prompt",
                "parent": "/",
                "menu_path": "/hello.txt",
                "src": ANY,
                "dest": ANY,
            },
        },
        "subhierarchies": {
            "subdir": {
                "entries": {
                    "hello.py": {
                        "menu_name": "hello.py",
                        "action": "copy",
                        "disposition": "prompt",
                        "parent": "/subdir",
                        "menu_path": "/subdir/hello.py",
                        "src": ANY,
                        "dest": ANY,
                    },
                    "hello.txt": {
                        "menu_name": "hello.txt",
                        "action": "copy",
                        "disposition": "prompt",
                        "parent": "/subdir",
                        "menu_path": "/subdir/hello.txt",
                        "src": ANY,
                        "dest": ANY,
                    },
                },
                "subhierarchies": {
                    "subsubdir": {
                        "entries": {
                            "hello.py": {
                                "menu_name": "hello.py",
                                "action": "copy",
                                "disposition": "prompt",
                                "parent": "/subdir/subsubdir",
                                "menu_path": "/subdir/subsubdir/hello.py",
                                "src": ANY,
                                "dest": ANY,
                            },
                            "hello.txt": {
                                "menu_name": "hello.txt",
                                "action": "copy",
                                "disposition": "prompt",
                                "parent": "/subdir/subsubdir",
                                "menu_path": "/subdir/subsubdir/hello.txt",
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

    h2 = HDLR._build_hierarchy(root=tutorial_env, suffix=".py")
    h2_p = h2.to_primitive()

    assert h2_p == {
        "entries": {
            "hello": {
                "menu_name": "hello",
                "action": "copy",
                "disposition": "prompt",
                "parent": "/",
                "menu_path": "/hello",
                "src": ANY,
                "dest": ANY,
            }
        },
        "subhierarchies": {
            "subdir": {
                "entries": {
                    "hello": {
                        "menu_name": "hello",
                        "action": "copy",
                        "disposition": "prompt",
                        "parent": "/subdir",
                        "menu_path": "/subdir/hello",
                        "src": ANY,
                        "dest": ANY,
                    }
                },
                "subhierarchies": {
                    "subsubdir": {
                        "entries": {
                            "hello": {
                                "menu_name": "hello",
                                "action": "copy",
                                "disposition": "prompt",
                                "parent": "/subdir/subsubdir",
                                "menu_path": "/subdir/subsubdir/hello",
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

    h3 = HDLR._build_hierarchy(
        root=tutorial_env,
        suffix=".txt",
        action=Actions.FETCH,
        xform_src=lambda x: f"https://example.com/foo/{Path(Path(x).name)}",
        xform_dest=lambda x: Path("bar"),
    )
    h3_p = h3.to_primitive()

    assert h3_p == {
        "entries": {
            "hello": {
                "menu_name": "hello",
                "action": "fetch",
                "disposition": "prompt",
                "parent": "/",
                "menu_path": "/hello",
                "src": "https://example.com/foo/hello.txt",
                "dest": "bar",
            }
        },
        "subhierarchies": {
            "subdir": {
                "entries": {
                    "hello": {
                        "menu_name": "hello",
                        "action": "fetch",
                        "disposition": "prompt",
                        "parent": "/subdir",
                        "menu_path": "/subdir/hello",
                        "src": "https://example.com/foo/hello.txt",
                        "dest": "bar",
                    }
                },
                "subhierarchies": {
                    "subsubdir": {
                        "entries": {
                            "hello": {
                                "menu_name": "hello",
                                "action": "fetch",
                                "disposition": "prompt",
                                "parent": "/subdir/subsubdir",
                                "menu_path": "/subdir/subsubdir/hello",
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


def test_ignore_symlinks(tutorial_env: Path) -> None:
    """We should just skip any symlinks we find, as a cheesy way of not having
    to deal with loops.
    """
    sl = Path(tutorial_env / "symlink")
    sl.mkdir()
    os.symlink(__file__, sl / "me")
    os.symlink(Path(__file__).parent, sl / "here")
    (sl / "real_file").write_text("Hello, world!\n")

    assert (sl / "me").is_symlink()
    assert (sl / "here").is_symlink()

    h = HDLR._build_hierarchy(sl)
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


def test_bad_construction() -> None:
    """Demonstrate that Hierarchy construction fails as it should."""

    @dataclass
    class TestInput:
        """Convenience class for constructor testing."""

        name: str
        value: dict[str, Any]
        match: str | None

    inp = [
        TestInput(name="missing_toplevel", value={}, match=None),
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
        TestInput(name="missing_toplevel", value={}, match=None),
        TestInput(
            name="malformed_entry",
            value={
                "menu_name": 4,
            },
            match="not a string",
        ),
        TestInput(
            name="extra_fields",
            value={
                "menu_name": "foo",
                "action": "a",
                "disposition": "b",
                "src": "c",
                "dest": "d",
                "parent": "/",
                "menu_path": "/foo",
                "extra_field": True,
            },
            match="Unknown fields",
        ),
        TestInput(
            name="bad_action",
            value={
                "menu_name": "foo",
                "action": "a",
                "disposition": "b",
                "src": "c",
                "dest": "d",
                "parent": "/",
                "menu_path": "/foo",
            },
            match=r"'action'=(.*): not in",
        ),
        TestInput(
            name="bad_disposition",
            value={
                "menu_name": "foo",
                "action": "copy",
                "disposition": "b",
                "src": "c",
                "dest": "d",
                "parent": "/",
                "menu_path": "/foo",
            },
            match=r"'disposition'=(.*): not in",
        ),
        TestInput(
            name="bad_menu_path",
            value={
                "menu_name": "foo",
                "action": "copy",
                "disposition": "abort",
                "src": "c",
                "dest": "d",
                "parent": "/bar",
                "menu_path": "/baz/bar/foo",
            },
            match="'menu_path' is",
        ),
    ]

    for tst in inp:
        with pytest.raises(HierarchyError, match=tst.match):
            _ = HierarchyEntry.from_primitive(tst.value)


def test_demonstrate_cache(tutorial_env: Path) -> None:
    """Demonstrate that the cache is appropriately populated."""
    now = time.time()
    assert HDLR._cache["timestamp"] > 0
    assert HDLR._cache["timestamp"] < now
    assert HDLR._cache["timestamp"] > now - 8.0 * 60 * 60
    assert HDLR._cache["hierarchy"] is not None
    assert HDLR._check_cache() is not None
