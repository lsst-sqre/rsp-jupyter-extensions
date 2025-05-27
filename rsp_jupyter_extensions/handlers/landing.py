"""Ensure that landing page is cached in user's homedir."""

from __future__ import annotations

import datetime
import os
import shutil
from pathlib import Path
from typing import Any

import tornado
from jupyter_server.base.handlers import APIHandler

from ..models.landing import LandingResponse
from ._utils import _get_homedir


class LandingPageHandler(APIHandler):
    """Provide a handler ensuring that the landing page is present so we
    can open it as the first thing a user sees.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        homedir = _get_homedir()
        self._cachedir = homedir / "notebooks" / "tutorials"
        self._cachedir.mkdir(exist_ok=True)
        self._landing_page = self._cachedir / "landing_page.md"
        self._files = (
            self._landing_page,
            self._cachedir / "logo_for_header.png",
        )
        self._dest = str(self._landing_page.relative_to(homedir))
        self.log.info("landing: server extension initialized")

    @tornado.web.authenticated
    def get(self) -> None:
        """Return a 200 and an empty document if we have the file in place.
        Otherwise, the errors will propagate out as a 500.
        """
        cached = self._check_landing_stash()
        if not cached:
            self.log.debug("landing: file copy required")
            self._copy_landing_files()
        retval = LandingResponse(dest=self._dest, cached=cached)
        self.write(dict(retval))

    def _check_landing_stash(self) -> bool:
        # This is a little subtle.  We get a new instance of the
        # handler with every access of its endpoints, and however
        # Jupyter Server manages that it really needs to be a new
        # one--making the handler a singleton does not work (it
        # doesn't respond to its endpoints).
        #
        # So what we do is to check the presence of the splash page
        # copy in a known location inside the user's homedir.  If it
        # exists and it is sufficiently new (let's start with 1 hour
        # or less), return True.
        max_age = datetime.timedelta(hours=1)
        now = datetime.datetime.now(tz=datetime.UTC)
        rval = True
        for stash in self._files:
            if not stash.is_file():
                rval = False
                break
            mod = datetime.datetime.fromtimestamp(
                stash.stat().st_mtime, tz=datetime.UTC
            )
            age = now - mod
            if age > max_age:
                rval = False
                break
        self.log.debug(f"landing: cache OK = {rval}")
        return rval

    def _copy_landing_files(self) -> None:
        # Copy the landing page files from their home to someplace we
        # can open the markdown within a user lab (must be within lab
        # starting directory, which in the RSP case is the user home
        # directory, and cannot be a dotfile because the Jupyter file
        # manager must be able to see it to open it).
        srcdir = Path(
            os.getenv(
                "CST_LANDING_PAGE_SRC_DIR",
                "/rubin/cst_repos/tutorial-notebooks-data/data",
            )
        )
        for fname in self._files:
            src = srcdir / fname.name
            self.log.debug(f"landing: copying {src!s} to {fname!s}")
            shutil.copy(src, fname)
