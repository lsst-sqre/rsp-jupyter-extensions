"""Test PDF export functionality, kind of.

We don't really want to enforce that typst be installed in the environment,
but on the other hand we don't need to really do the conversion.  So
we will install a fake typst that appears to run correctly, but doesn't
really convert anything.
"""

import contextlib
import os
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import tornado

from rsp_jupyter_extensions.handlers.pdfexport import PDFExportHandler


@pytest.fixture
def _fake_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    data_dir = Path(__file__).parent / "data"
    t_home = Path(tmp_path) / "home" / "hambone"
    t_home.mkdir(parents=True)
    homedir = str(t_home)
    monkeypatch.setenv("JUPYTER_SERVER_ROOT", homedir)
    exp_path = tmp_path / "bin"
    exp_path.mkdir()
    # Make that the first thing in PATH
    path = os.getenv("PATH", "")
    monkeypatch.setenv("PATH", f"{exp_path!s}:{path}")
    # Copy fake "typst" to fake_root/bin.
    typst = exp_path / "typst"
    pandoc = exp_path / "pandoc"
    shutil.copy2((data_dir / "typst"), typst)
    shutil.copy2((data_dir / "pandoc"), pandoc)
    # Copy fake notebook to fake_root/homedir
    shutil.copy2(data_dir / "nb.ipynb", t_home)
    yield
    # Pretend we have some cleanup to make linter happy
    if (exp_path / "typst").exists():
        if typst.is_dir():
            typst.rmdir()
        else:
            typst.unlink()
    if (exp_path / "pandoc").exists():
        if pandoc.is_dir():
            pandoc.rmdir()
        else:
            pandoc.unlink()


class _FakeConnect(tornado.httputil.HTTPConnection):
    def set_close_callback(self, arg: Any) -> None:
        pass


@pytest.mark.usefixtures("_fake_root")
@pytest.mark.asyncio
async def test_export() -> None:
    homedir = os.getenv("JUPYTER_SERVER_ROOT", "")
    with contextlib.chdir(homedir):
        handler = PDFExportHandler(
            tornado.web.Application(),
            request=tornado.httputil.HTTPServerRequest(
                connection=_FakeConnect()
            ),
        )

        # Happy path
        bindir = Path(homedir).parent.parent / "bin"
        pathdir = os.getenv("PATH", "").split(":")[0]
        assert pathdir == str(bindir)
        resp = await handler._to_pdf_response("nb.ipynb")
        assert resp.path == "nb.pdf"
        pdf = Path(homedir) / "nb.pdf"
        assert (pdf).read_text() == "Ceci pas un PDF document."


@pytest.mark.usefixtures("_fake_root")
@pytest.mark.asyncio
async def test_missing_notebook() -> None:
    homedir = os.getenv("JUPYTER_SERVER_ROOT", "")
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
    homedir = os.getenv("JUPYTER_SERVER_ROOT", "")
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
    homedir = os.getenv("JUPYTER_SERVER_ROOT", "")
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
async def test_no_typst() -> None:
    homedir = os.getenv("JUPYTER_SERVER_ROOT", "")
    with contextlib.chdir(homedir):
        handler = PDFExportHandler(
            tornado.web.Application(),
            request=tornado.httputil.HTTPServerRequest(
                connection=_FakeConnect()
            ),
        )

        # No typst
        (Path(homedir).parent.parent / "bin" / "typst").unlink()
        if shutil.which("typst") is not None:
            pytest.skip("typst is really installed")
        resp = await handler._to_pdf_response("nb.ipynb")
        assert resp.error is not None
        assert resp.error.startswith("No executable 'typst'")


@pytest.mark.usefixtures("_fake_root")
@pytest.mark.asyncio
async def test_no_pandoc() -> None:
    homedir = os.getenv("JUPYTER_SERVER_ROOT", "")
    with contextlib.chdir(homedir):
        handler = PDFExportHandler(
            tornado.web.Application(),
            request=tornado.httputil.HTTPServerRequest(
                connection=_FakeConnect()
            ),
        )

        # No pandoc
        (Path(homedir).parent.parent / "bin" / "pandoc").unlink()
        if shutil.which("pandoc") is not None:
            pytest.skip("pandoc is really installed")
        resp = await handler._to_pdf_response("nb.ipynb")
        assert resp.error is not None
        assert resp.error.startswith("No executable 'pandoc'")
