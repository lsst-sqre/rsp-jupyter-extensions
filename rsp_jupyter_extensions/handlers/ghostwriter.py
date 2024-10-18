from jupyter_server.base.handlers import JupyterHandler


class Ghostwriter_handler(JupyterHandler):
    """
    Ghostwriter handler.  Used to handle the case where Ghostwriter runs
    ensure_lab and no lab is running: the original redirection is
    changed to point at this endpoint within the lab, and this just
    issues the redirect back to the root path.  But this time, enable_lab
    will realize the lab is indeed running, and the rest of the flow will
    proceed.

    We should only ever get GETs and POSTs.
    """

    def get(self) -> None:
        self.redirect(self._peel_route())

    def put(self) -> None:
        self.redirect(self._peel_route())

    def post(self) -> None:
        self.redirect(self._peel_route())

    def delete(self) -> None:
        self.redirect(self._peel_route())

    def head(self) -> None:
        self.redirect(self._peel_route())

    def patch(self) -> None:
        self.redirect(self._peel_route())

    def options(self) -> None:
        self.redirect(self._peel_route())

    def _peel_route(self) -> None:
        """Return the stuff after '/rubin/ghostwriter' as the top-level
        path.  This will send the requestor back to the original location,
        where this time, the running_lab check will succeed and they will
        wind up where they should."""
        bad_route = "/nb"  # In case of failure, dump to lab?  I guess?
        path = self.request.path
        stem = "/rubin/ghostwriter/"
        pos = path.find(stem)
        if pos == -1:
            # We didn't match.
            return bad_route
        idx = len(stem) + pos - 1
        redir = path[idx:]
        if redir.startswith(stem):
            # This is gonna be a redirect loop.
            return bad_route
        return redir
