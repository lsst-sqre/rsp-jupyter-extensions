"""Test construction of representation of tree for tutorial notebooks."""

from dataclasses import dataclass
from typing import Any

import pytest

from rsp_jupyter_extensions.models.tutorials import (
    Hierarchy,
    HierarchyEntry,
    HierarchyError,
)


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
