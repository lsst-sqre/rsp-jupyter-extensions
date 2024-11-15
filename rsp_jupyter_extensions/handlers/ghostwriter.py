"""Ghostwriter handler, used for redirection bank shots once you've
started a new lab."""

from typing import Any

from jupyter_server.base.handlers import JupyterHandler


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
    """

    async def prepare(self, *, _redirect_to_login: Any = ...) -> None:
        self.redirect(self._peel_route())

    def _peel_route(self) -> str:
        """Return the stuff after '/rubin/ghostwriter' as the top-level
        path.  This will send the requestor back to the original location,
        where this time, the running_lab check will succeed and they will
        wind up where they should."""
        bad_route = "/nb"  # In case of failure, dump to lab?  I guess?
        path = self.request.path
        self.log.info(f"Ghostwriter method '{self.request.method}'," f" path '{path}'")
        stem = "/rubin/ghostwriter/"
        pos = path.find(stem)
        if pos == -1:
            # We didn't match.
            return bad_route
        idx = len(stem) + pos - 1
        redir = path[idx:]
        if not redir or redir == "/" or redir.startswith(stem):
            self.log.warning(
                f"Request for bad redirection '{redir}';"
                f" returning '{bad_route}' instead"
            )
            return bad_route
        return redir
