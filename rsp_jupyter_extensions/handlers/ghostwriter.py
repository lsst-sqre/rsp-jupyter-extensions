"""Ghostwriter handler, used for redirection bank shots once you've
started a new lab.
"""

import os
from urllib.parse import urljoin

from jupyter_server.base.handlers import JupyterHandler

from ._utils import _peel_route


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

    def prepare(self) -> None:  # type: ignore[override]
        """Issue a redirect based on the request path."""
        # the implicit None return can also function as a null coroutine,
        # and in Python 3.13, "None" becomes a valid return type from it.
        #
        # So once we're at Python 3.13, we can remove that type: ignore.
        redir = _peel_route(self.request.path, "/rubin/ghostwriter")
        # If we don't have EXTERNAL_INSTANCE_URL, we don't have ghostwriter.
        # Just crash the handler, I guess?  It'll look like a no-op to the
        # user with some nastiness in the browser console.
        ext_url = os.environ["EXTERNAL_INSTANCE_URL"]
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
