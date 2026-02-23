"""Utilities for working with Jupyter Server RSP handlers."""

import json
import os
from contextlib import suppress
from pathlib import Path
from typing import Any

_CONFIG_FILE = Path("/etc/nublado/config/lab-config.json")


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


def _get_config(path: Path = _CONFIG_FILE) -> dict[str, Any]:
    """Return the config object."""
    return json.loads(path.read_text())


def _file_to_browser_path(path: Path) -> str | None:
    """Given the filesystem path of a file, return the corresponding route
    for that file to be opened in the Lab, or None if that file is not
    accessible via the file browser.
    """
    obj = _get_config()
    top = obj["file_browser_root"]
    comparator = Path("/")
    if top == "home":
        comparator = Path(os.environ["HOME"])  # Lab won't start without $HOME
    try:
        return str(path.relative_to(comparator))
    except ValueError:
        return None


def _browser_path_to_file(path: str) -> Path:
    """Given a browser path, return the absolute file path."""
    obj = _get_config()
    top = obj["file_browser_root"]
    comparator = Path("/")
    if top == "home":
        comparator = Path(os.environ["HOME"])
    return comparator / Path(path)


def _browser_path_to_tree(path: str) -> str:
    """Given a path in the Lab filebrowser, return a route under /tree that
    will open the corresponding file.
    """
    pref = os.environ.get("JUPYTERHUB_SERVICE_PREFIX", "")
    return f"{pref.rstrip('/')}/tree/{path}"


def _write_notebook_response(nb_text: str, target: Path) -> str:
    """Given notebook text and a filename where it should go, return
    a response for Jupyter to give back to the extension to open that file
    in the JupyterLab UI.
    """
    dirname = target.parent
    fname = target.name
    dirname.mkdir(parents=True, exist_ok=True)
    target.write_text(nb_text)
    rel_path = _file_to_browser_path(target)
    if rel_path is None:
        raise ValueError(
            f"{target!s} cannot be represented in the Lab file browser."
        )
    route = _browser_path_to_tree(rel_path)

    retval = {
        "status": 200,
        "filename": fname,
        "path": rel_path,
        "url": route,
        "body": nb_text,
    }
    return json.dumps(retval)


def _get_access_token(
    tokenfile: str | Path | None = None, log: Any | None = None
) -> str:
    """Get the Gafaelfawr access token for the user.

    Determine the access token from the mounted location (nublado 3/2) or
    environment (any).  Prefer the mounted version since it can be updated,
    while the environment variable stays at whatever it was when the process
    was started.  Return the empty string if the token cannot be determined.
    """
    if tokenfile:
        token = ""
        with suppress(Exception):
            token = Path(tokenfile).read_text().strip()
        return token

    base_dir: Path | None = None
    with suppress(Exception):
        obj = _get_config()
        base_dir = Path(obj["runtime_mounts_dir"])
    if base_dir:
        for candidate in (
            base_dir / "secrets" / "token",
            base_dir / "environment" / "ACCESS_TOKEN",
        ):
            with suppress(FileNotFoundError):
                return candidate.read_text().strip()

    # If we got here, we couldn't find a file. Return the environment variable
    # if set, otherwise the empty string.
    return os.environ.get("ACCESS_TOKEN", "")
