"""Test construction of representation of tree for tutorial notebooks."""

import tempfile
import time
from pathlib import Path

import pytest
import tornado

import rsp_jupyter_extensions.handlers.tutorials as t

from ..._fake import _FakeConnect


@pytest.mark.asyncio
async def test_demonstrate_cache(
    tutorial_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Demonstrate that the cache is appropriately populated."""
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        Path.mkdir(tdir / ".git")
        (tdir / "README.md").write_text("# README\n")
        with monkeypatch.context() as mp:
            mp.setenv("TUTORIAL_NOTEBOOKS_CACHE_DIR", td)
            new_hdlr = t.TutorialsMenuHandler(
                tornado.web.Application(),
                request=tornado.httputil.HTTPServerRequest(
                    connection=_FakeConnect()
                ),
            )
            assert new_hdlr._cache["timestamp"] == 0
            await new_hdlr._populate_tutorials()
            now = time.time()
            assert new_hdlr._cache["timestamp"] > 0
            assert new_hdlr._cache["timestamp"] <= now
            assert new_hdlr._cache["timestamp"] > now - 8.0 * 60 * 60
            assert new_hdlr._cache["hierarchy"] is not None
            assert new_hdlr._check_cache() is not None
