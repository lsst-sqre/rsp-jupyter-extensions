"""Utilities for working with Jupyter Server RSP handlers."""

import json
import os
from pathlib import Path

from ..models.tutorials import UserEnvironmentError


def _get_homedir() -> Path:
    homedir = os.getenv("HOME")
    if not homedir:
        raise UserEnvironmentError("home directory is not set")
    return Path(homedir)


def _get_jupyter_server_root() -> Path:
    # We can't use JUPYTER_SERVER_ROOT, as it's set by the JupyterLab process
    # for the subprocesses it spawns, but not in the parent process.
    srv_root = os.getenv("FILEBROWSER_ROOT", "home")
    if srv_root == "root":
        return Path("/")
    return _get_homedir()


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
    # JUPYTER_SERVER_ROOT is set *by* JupyterLab, not in its environment.
    rname = target.relative_to(_get_jupyter_server_root())
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
