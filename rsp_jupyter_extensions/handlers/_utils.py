"""Utilities for working with Jupyter Server RSP handlers."""

import json
import os
from pathlib import Path


def _peel_route(path: str, stem: str) -> str | None:
    # Return the part of the route after the stem, or None if that doesn't
    # work.
    pos = path.find(stem)
    if pos == -1:
        # We didn't match.
        return None
    idx = len(stem) + pos
    shorty = path[idx:]
    if not shorty or shorty == "/" or shorty.startswith(stem):
        return None
    return shorty


def _write_notebook_response(nb_text: str, target: Path) -> str:
    """Given notebook text and a filename where it should go, return
    a response for Jupyter to give back to the extension to open that file
    in the JupyterLab UI.
    """
    dirname = target.parent
    fname = target.name
    rname = target.relative_to(Path(os.getenv("JUPYTER_SERVER_ROOT", "")))
    dirname.mkdir(parents=True, exist_ok=True)
    target.write_text(nb_text)
    top = os.environ.get("JUPYTERHUB_SERVICE_PREFIX", "")
    retval = {
        "status": 200,
        "filename": str(fname),
        "path": str(rname),
        "url": f"{top}/tree/{rname!s}",
        "body": nb_text,
    }
    return json.dumps(retval)
