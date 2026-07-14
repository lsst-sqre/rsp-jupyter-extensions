"""Handler Module to provide an endpoint for PDF Export of a notebook."""

import json
from contextlib import chdir
from pathlib import Path
from textwrap import dedent

import tornado
import typst

from ..models.pdfexport import PDFExportResponse
from ._base import _BaseRSPAPIHandler


class PDFExportHandler(_BaseRSPAPIHandler):
    """Convert notebook to PDF.

    This approach relies on typst, which is a single (albeit hefty) binary
    and a little bit of Python glue (pip-installable), and callisto, which
    is a downloadable typst module.  If your notebook doesn't have access to
    the internet, this is going to fail.

    We might be able to fix this at build time by downloading callisto and
    shoving it someplace we know, and then importing from there.
    """

    def initialize(self) -> None:
        """Set rootdir."""
        super().initialize()
        self._root_dir: Path | None = None

    @tornado.web.authenticated
    async def post(self, *args: str, **kwargs: str) -> None:
        """POST receives the query type and the query value as a JSON
        object containing "path" key.  It is a string, and should be
        a relative path (that is, should not start with "/" and should
        expect to be appended to self._root_dir); self._root_dir may be
        either / or $HOME.

        Having resolved the filename, if it exists and the directory
        is writeable, we will change directory to where that file
        resides (on the grounds that if it uses relative paths for
        things it links, we want those paths to work).  We then
        construct a very short typst document that reads the requested
        notebook, and then we compile that typst document, which will
        yield (if all goes well) a PDF next to the notebook.

        We then return that path to the caller, as the "path" key of a
        JSON document.  The caller then can display or download the file.

        """
        input_str = self.request.body.decode("utf-8")
        input_document = json.loads(input_str)
        nb_path = input_document["path"]
        pdf_path_doc = await self._convert_document(nb_path)
        self.write(pdf_path_doc)

    async def _convert_document(self, nb_path: str) -> str:
        """Delegate the conversion, and stringify the response."""
        return (await self._to_pdf_response(nb_path)).to_str()

    async def _to_pdf_response(self, nb_path: str) -> PDFExportResponse:
        """Sanity-check the inputs, make the PDF, report."""
        obj = PDFExportResponse()
        if self._root_dir is None:
            self._root_dir = await self._get_jupyter_server_root()
        nb = self._root_dir / nb_path
        if not nb.exists():
            obj.error = f"File {nb} does not exist"
            return obj
        if not nb.name.endswith(".ipynb"):
            # Not totally sure we wish to enforce this.
            obj.error = f"File {nb} does not end with .ipynb; not a notebook"
            return obj
        try:
            await self._try_callisto(nb)
        except Exception as exc:
            self.log.exception(f"PDF conversion of {nb!s} failed")
            obj.error = f"PDF conversion of {nb!s} failed: {exc!s}"
            return obj
        # Success: no error, path points to PDF.
        pdf = nb.parent / f"{nb.stem}.pdf"
        obj.path = f"{pdf.relative_to(self._root_dir)!s}"
        return obj

    async def _try_callisto(self, nb: Path) -> None:
        # Callisto works with CST inline images as of 0.3.0.
        # Create a tiny typst wrapper pointing at the notebook.
        cconfig = f'callisto.config(nb: path("{nb.stem}.ipynb"))'
        typbytes = dedent(
            f"""
            #import "@preview/callisto:0.3.0"
            #let (render, Cell, In, Out) = {cconfig}
            #render()
            """
        ).encode()
        with chdir(nb.parent):
            op = f"{nb.stem}.pdf"
            # The Input type var *should* be able to be bytes:
            # see https://github.com/messense/typst-py/blob/\
            #  03f4bc454153e9c532f6122ca440cc9006a833ff/python/typst/\
            #  __init__.pyi#L6
            typst.compile(typbytes, output=op)  # type: ignore [type-var]
