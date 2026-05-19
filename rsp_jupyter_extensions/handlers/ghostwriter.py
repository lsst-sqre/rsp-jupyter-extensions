"""Ghostwriter handler, used for redirection bank shots once you've
started a new lab.
"""

import os
from urllib.parse import urljoin

from jupyter_server.base.handlers import JupyterHandler

from ..exceptions import UnknownInstanceError
from ._utils import _peel_route
from .clients import RSPClient


class GhostwriterHandler(JupyterHandler):
    """
    Used to handle the case where Ghostwriter runs ensure_lab and no
    lab is running: the original redirection is changed to point at
    this endpoint within the lab, and this just issues the redirect
    back to the external Ghostwriter-managed root path.  But this
    time, enable_lab will realize the lab is indeed running, and the
    rest of the flow will proceed.

    All of this can happen in prepare(), because we don't care what method
    it is.

    Note that this endpoint is *not* an APIHandler, because we're not
    handing back a JSON document; this is an endpoint for the browser to
    use to receive a redirection.
    """

    def initialize(self) -> None:
        super().initialize()
        cname = self.__class__.__name__
        self._logger = self.log
        if "client" not in self.settings:
            self._logger.info(f"Initializing RSP Client for {cname}")
            self.settings["client"] = RSPClient(logger=self.log)
        self._rsp_client = self.settings["client"]

    async def prepare(self, *, _redirect_to_login: bool = True) -> None:
        """Issue a redirect based on the request path."""
        redir = _peel_route(self.request.path, "/rubin/ghostwriter")
        # Try to get the URL for the landing page of our RSP instance.
        # Fall back to EXTERNAL_INSTANCE_URL if we fail.
        # Crash if we don't have that, and that will put something in the
        # logs pointing us in the right direction.
        ext_url = await self._rsp_client.get_squareone_url()
        if not ext_url:
            ext_url = os.environ.get("EXTERNAL_INSTANCE_URL")
        if not ext_url:
            raise UnknownInstanceError("Cannot determine RSP instance URL")
        if redir:
            # We want to go all the way back out to the top level and
            # hit the external ghostwriter redirect again.
            self.redirect(urljoin(ext_url, redir))
        else:
            self.log.warning(
                f"Cannot strip '/rubin/ghostwriter' from '{self.request.path}'"
                f" ; returning a redirection to the Hub instead"
            )
            # $JUPYTERHUB_PUBLIC_HUB_URL is unset if user domains are not
            # enabled, and therefore "/nb" will point us to the Hub...
            # and the Hub will drop us back in the running Lab.
            self.redirect(os.getenv("JUPYTERHUB_PUBLIC_HUB_URL", "/nb"))
