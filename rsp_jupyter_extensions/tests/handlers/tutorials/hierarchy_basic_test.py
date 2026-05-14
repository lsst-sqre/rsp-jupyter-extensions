"""Test construction of representation of tree for tutorial notebooks."""

from pathlib import Path
from unittest.mock import ANY

import pytest
import tornado

import rsp_jupyter_extensions.handlers.tutorials as t
from rsp_jupyter_extensions.models.tutorials import (
    Actions,
    Hierarchy,
)

from ..._fake import _FakeConnect


def test_basic_hierarchy(
    tutorial_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test _build_hierarchy(), which underpins the tutorial extension.

    Create three different views of the same filesystem, and roundtrip each
    one through serialization and back.
    """
    handler = t.TutorialsMenuHandler(
        tornado.web.Application(),
        request=tornado.httputil.HTTPServerRequest(connection=_FakeConnect()),
    )
    monkeypatch.setenv(
        "REPERTOIRE_BASE_URL", "https://example.lsst.cloud/repertoire"
    )
    h1 = handler._build_hierarchy(root=tutorial_env)
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

    h2 = handler._build_hierarchy(root=tutorial_env, suffix=".py")
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

    h3 = handler._build_hierarchy(
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
