"""Utilities for working with Jupyter Server RSP handlers."""

import os
from pathlib import Path

from ..exceptions import UserEnvironmentError


def _get_homedir() -> Path:
    homedir = os.getenv("HOME")
    if not homedir:
        raise UserEnvironmentError("home directory is not set")
    return Path(homedir)


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
