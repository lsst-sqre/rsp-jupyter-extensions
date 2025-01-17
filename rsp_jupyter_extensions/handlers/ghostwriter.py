"""Ghostwriter handler, used for redirection bank shots once you've
started a new lab.
"""
from jupyter_server.base.handlers import JupyterHandler

from ._utils import _peel_route


class GhostwriterHandler(JupyterHandler):
    """
    Ghostwriter handler.  Used to handle the case where Ghostwriter runs
    ensure_lab and no lab is running: the original redirection is
    changed to point at this endpoint within the lab, and this just
    issues the redirect back to the root path.  But this time, enable_lab
    will realize the lab is indeed running, and the rest of the flow will
    proceed.

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
        redir = _peel_route(self.request.path, "/rubin/ghostwriter")
        if redir:
            self.redirect(redir)
        else:
            self.log.warning(
                f"Cannot strip '/rubin/ghostwriter' from '{self.request.path}'"
                f" ; returning '/nb' instead"
            )
            self.redirect("/nb")
