"""Utilities for working with Jupyter Server RSP handlers."""

import os
from contextlib import suppress
from pathlib import Path

from ..exceptions import TokenNotAvailableError, UserEnvironmentError


def _get_access_token() -> str:
    """Get our access token, preferred methods first."""
    # We want this to be a constant static path, but...
    path = Path("/etc/nublado/secrets/token")
    if path.exists():
        return path.read_text().strip()
    # ... in April 2026 it is not yet, but NUBLADO_RUNTIME_MOUNTS_DIR should
    # be set.
    if runtime_dir := os.environ.get("NUBLADO_RUNTIME_MOUNTS_DIR"):
        path = Path(runtime_dir) / "secrets" / "token"
        with suppress(FileNotFoundError):
            return path.read_text().strip()
    raise TokenNotAvailableError("No access token available")


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
