"""Handler Module to provide an endpoint for PDF Export of a notebook."""

import asyncio
import contextlib
import json
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

import tornado
from jupyter_server.base.handlers import APIHandler


@dataclass
class PDFExportResponse:
    """Simple wrapper for the response we will return to the caller.

    It has a "path" key and an "error" key.  If "path" is valid, "error" is
    ``None``, and vice versa.
    """

    path: str | None = None
    error: str | None = None

    def to_str(self) -> str:
        """Return JSON-serialized version of response."""
        self._validate()
        return json.dumps(asdict(self))

    def _validate(self) -> None:
        """Enforce that exactly one of the two fields is ``None``."""
        if self.path is None and self.error is None:
            self.error = "Both 'path' and 'error' cannot be 'None'"
        elif self.path is not None and self.error is not None:
            # The fact that there's an error invalidates the path.
            self.path = None


class PDFExportHandler(APIHandler):
    """Convert notebook to PDF.

    The current approach relies on pandoc, which is fairly heavyweight, but
    at least it does't require a full TeX stack or Chromium+Playwright
    installation.

    Typst is a single binary.  If we reach an agreement with CST about their
    inline images (or figure out a preprocessing step to strip them), we could
    use typst and let it download callisto to do our notebook rendering, which
    would be very fast and lightweight.
    """

    def initialize(self) -> None:
        """Set rootdir."""
        super().initialize()
        self._root_dir = Path(os.getenv("JUPYTER_SERVER_ROOT", ""))

    @tornado.web.authenticated
    async def post(self, *args: str, **kwargs: str) -> None:
        """POST receives the query type and the query value as a JSON
        object containing "path" key.  It is a string, and should be
        a relative path (that is, should not start with "/" and should
        expect to be appended to $JUPYTER_SERVER_ROOT (self._rootdir);
        in the current RSP setup, that's the same as $HOME, but that may
        change if we figure out how to get jupyter-server-documents and
        thus collaborative editing stable.

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
        """Sanity-check the executables and inputs, make the PDF, report."""
        obj = PDFExportResponse()
        typst = shutil.which("typst")
        pandoc = shutil.which("pandoc")
        if pandoc is None:
            path = os.getenv("PATH", "")
            obj.error = f"No executable 'pandoc' found on PATH ({path})"
            return obj
        if typst is None:
            path = os.getenv("PATH", "")
            obj.error = f"No executable 'typst' found on PATH ({path})"
            return obj
        nb = self._root_dir / nb_path
        if not nb.exists():
            obj.error = f"File {nb} does not exist"
            return obj
        if not nb.name.endswith(".ipynb"):
            # Not totally sure we wish to enforce this.
            obj.error = f"File {nb} does not end with .ipynb; not a notebook"
            return obj
        try:
            basename = f"{nb.name[: -(len('.ipynb'))]}"
            pdf = nb.parent / f"{basename}.pdf"
            with contextlib.chdir(self._root_dir):
                await self._try_pandoc(nb, pdf)
        except Exception as exc:
            self.log.exception(f"PDF conversion of {nb!s} failed")
            obj.error = f"PDF conversion of {nb!s} failed: {exc!s}"
            return obj
        # Success: no error, path points to PDF.
        obj.path = f"{pdf.relative_to(self._root_dir)!s}"
        return obj

    async def _try_pandoc(self, nb: Path, pdf: Path) -> None:
        # Asyncio subprocess makes chaining commands pretty
        # grotesque, alas.
        pipe_read, pipe_write = os.pipe()
        await asyncio.create_subprocess_exec(
            "pandoc", nb.name, "-w", "typst", stdout=pipe_write
        )
        os.close(pipe_write)
        proc = await asyncio.create_subprocess_exec(
            "typst",
            "compile",
            "-",
            pdf.name,
            stdin=pipe_read,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        os.close(pipe_read)
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"'typst compile - {pdf.name}' exited"
                f" with rc={proc.returncode}\n"
                f" stdout={stdout.decode()}\n",
                f" stderr={stderr.decode()}",
            )

    async def _try_callisto(self, nb: Path, pdf: Path) -> None:
        # This would be our preferred approach, but it dies with CST
        # inline images.  If it works it's great and extremely lightweight,
        # though.  Maybe we can reach a compromise with CST.
        basename = f"{nb.name[: -(len('.ipynb'))]}"
        typ = nb.parent / f"__{basename}.typ"
        typtext = '#import "@preview/callisto:0.2.4"\n'
        typtext += f'#callisto.render(nb: json("{nb.name}"))\n'
        typ.write_text(typtext)
        proc = await asyncio.create_subprocess_exec(
            "typst",
            "compile",
            str(typ),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"'typst compile {typ!s}' exited"
                f" with rc={proc.returncode}\n"
                f" stdout={stdout.decode()}\n",
                f" stderr={stderr.decode()}",
            )
        typ.unlink()
