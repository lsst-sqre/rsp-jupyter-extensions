"""Ensure that landing page is cached in user's homedir."""

from __future__ import annotations

import datetime
import json
import os
import shutil
from pathlib import Path

import tornado
from jupyter_server.base.handlers import APIHandler

from ._utils import _get_homedir

_FILES = ("landing_page.md", "logo_for_header.png")


def _check_landing_stash() -> bool:
    # This is a little subtle.  We get a new instance of the handler with
    # every access of its endpoints, and however Jupyter Server manages that
    # it really needs to be a new one--making the handler a singleton does
    # not work (it doesn't respond to its endpoints).
    #
    # So what we do is to check the presence of the splash page copy
    # in a known location inside the user's homedir.  If it exists and
    # it is sufficiently new (let's start with 1 hour or less), return True.
    max_age = datetime.timedelta(hours=1)
    cachedir = _get_homedir() / ".cache"
    now = datetime.datetime.now(tz=datetime.UTC)
    for fname in _FILES:
        stash = cachedir / fname
        if not stash.is_file():
            return False
        mod = datetime.datetime.fromtimestamp(
            stash.stat().st_mtime, tz=datetime.UTC
        )
        age = now - mod
        if age > max_age:
            return False
    return True


def _copy_landing_files() -> None:
    # Copy the landing page files from their home to someplace we can open
    # the markdown within a user lab (must be within lab starting directory,
    # which in the RSP case is the user home directory).
    srcdir = Path(
        os.getenv(
            "CST_LANDING_PAGE_SRC_DIR",
            "/rubin/cst_repos/tutorial-notebooks-data/data",
        )
    )
    cachedir = _get_homedir() / ".cache"
    cachedir.mkdir(exist_ok=True)
    for fname in _FILES:
        shutil.copy(srcdir / fname, cachedir / fname)


class LandingPageHandler(APIHandler):
    """Provide a handler ensuring that the landing page is present so we
    can open it as the first thing a user sees.
    """

    @tornado.web.authenticated
    def get(self) -> None:
        """Return a 200 and an empty document if we have the file in place.
        Otherwise, the errors will propagate out as a 500.
        """
        if not _check_landing_stash():
            _copy_landing_files()
        self.write(json.dumps({}))
