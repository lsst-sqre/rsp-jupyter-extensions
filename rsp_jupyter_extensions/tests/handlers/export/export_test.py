"""Test PDF export functionality.

Typst is now pip-installable, so we can guarantee it is available in the
environment.
"""

import contextlib
import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
import tornado

from rsp_jupyter_extensions.handlers.pdfexport import PDFExportHandler

from ..._fake import _FakeConnect


@pytest.fixture
def _fake_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Simulate an RSP filesystem.  We cannot use pyfakefs because
    typst-py is a native Rust extension bound with PyO3, and it uses real
    syscalls.  The fakefs patches Python's 'io', and so works at a level
    above where typst-py hooks in to the filesystem.
    """
    monkeypatch.setenv(
        "REPERTOIRE_BASE_URL", "https://example.lsst.cloud/repertoire"
    )
    data_dir = Path(__file__).parent.parent.parent / "data"
    for directory in ("home", "usr"):
        shutil.copytree(data_dir / directory, tmp_path / directory)
    old_home = os.getenv("HOME")
    assert old_home is not None
    t_home = tmp_path / "home" / "irian"
    homedir = str(t_home)
    monkeypatch.setenv("HOME", homedir)
    yield
    # Pretend we have some cleanup to make linter happy
    monkeypatch.setenv("HOME", old_home)


@pytest.mark.usefixtures("_fake_root")
@pytest.mark.asyncio
async def test_export() -> None:
    """Test PDF export via typst/callisto."""
    homedir = Path(os.environ["HOME"])
    refdir = Path(__file__).parent.parent.parent / "data" / "output"
    with contextlib.chdir(homedir):
        handler = PDFExportHandler(
            tornado.web.Application(),
            request=tornado.httputil.HTTPServerRequest(
                connection=_FakeConnect()
            ),
        )
        # We have multiple files to test here.  One is a minimal notebook,
        # and the other uses an embedded image as CST tutorials do.
        nbs = list(homedir.glob("*.ipynb"))
        assert nbs  # We better have at least one.
        for fn in nbs:
            # Happy path
            resp = await handler._to_pdf_response(fn.name)
            assert resp.path == f"{fn.stem}.pdf"
            pdf = homedir / f"{fn.stem}.pdf"
            ref = refdir / f"{fn.stem}.pdf"
            assert pdf.exists()
            assert ref.exists()
            # The files are not identical; not only do the things you'd
            # expect to differ, like the timestamp and unique document ID
            # vary, but the output also depends on what system fonts you
            # have installed and other stuff; notably, Mac and Linux do
            # not produce particularly similar results.
            #
            # So we're going to ensure that each file is at least 1K,
            # that it starts with "%PDF-", that the file sizes are within
            # 10% of each other, and call it a day.
            # Which is indeed not very exact, but, well, it
            # generated something substantial.
            #
            psize = pdf.stat().st_size
            rsize = ref.stat().st_size
            delta = abs(psize - rsize)
            assert psize > 1024
            assert rsize > 1024
            with pdf.open("rb") as f:
                p5 = f.read(5)
            with ref.open("rb") as f:
                r5 = f.read(5)
            assert p5 == r5 == b"%PDF-"
            assert 10 * delta < psize


@pytest.mark.usefixtures("_fake_root")
@pytest.mark.asyncio
async def test_missing_notebook() -> None:
    homedir = Path(os.environ["HOME"])
    with contextlib.chdir(homedir):
        handler = PDFExportHandler(
            tornado.web.Application(),
            request=tornado.httputil.HTTPServerRequest(
                connection=_FakeConnect()
            ),
        )

        # No such input
        resp = await handler._to_pdf_response("nope.ipynb")
        assert resp.error is not None
        assert resp.error.endswith("does not exist")


@pytest.mark.usefixtures("_fake_root")
@pytest.mark.asyncio
async def test_output_is_directory() -> None:
    homedir = Path(os.environ["HOME"])
    with contextlib.chdir(homedir):
        handler = PDFExportHandler(
            tornado.web.Application(),
            request=tornado.httputil.HTTPServerRequest(
                connection=_FakeConnect()
            ),
        )

        pdf = Path(homedir) / "nb.pdf"
        # Output exists and is a directory
        if pdf.exists():
            if pdf.is_dir():
                pdf.rmdir()
            else:
                pdf.unlink()
        pdf.mkdir()
        resp = await handler._to_pdf_response("nb.ipynb")
        assert resp.error is not None
        assert resp.error.startswith("PDF conversion of")
        pdf.rmdir()


@pytest.mark.usefixtures("_fake_root")
@pytest.mark.asyncio
async def test_input_is_not_notebook() -> None:
    homedir = Path(os.environ["HOME"])
    with contextlib.chdir(homedir):
        handler = PDFExportHandler(
            tornado.web.Application(),
            request=tornado.httputil.HTTPServerRequest(
                connection=_FakeConnect()
            ),
        )
        # Not a notebook
        (Path(homedir) / "nope.txt").write_text("Not a notebook")
        resp = await handler._to_pdf_response("nope.txt")
        assert resp.error is not None
        assert resp.error.endswith(
            "nope.txt does not end with .ipynb; not a notebook"
        )


@pytest.mark.usefixtures("_fake_root")
@pytest.mark.asyncio
async def test_bad_notebook() -> None:
    homedir = Path(os.environ["HOME"])
    with contextlib.chdir(homedir):
        handler = PDFExportHandler(
            tornado.web.Application(),
            request=tornado.httputil.HTTPServerRequest(
                connection=_FakeConnect()
            ),
        )
        # Named like a notebook, but not a notebook structure.
        (Path(homedir) / "nope.ipynb").write_text("Not a notebook")
        resp = await handler._to_pdf_response("nope.ipynb")
        assert resp.error is not None
        assert resp.error.endswith(
            "failed to parse JSON (expected value at line 1 column 1)"
        )
