"""Synchronous RSP Client for use in server extension handlers."""

from typing import Any
from urllib.parse import urljoin

import lsst.rsp
import requests


class RSPClient(requests.Session):
    """Subclassed Session to add base_url and authentication.

    cf. https://stackoverflow.com/questions/42601812
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        base_path = kwargs.pop("base_path", None)
        super().__init__(*args, **kwargs)
        token = lsst.rsp.get_access_token()
        instance_url = (
            (
                lsst.rsp.utils.get_runtime_mounts_dir()
                / "environment"
                / "EXTERNAL_INSTANCE_URL"
            )
            .read_text()
            .strip()
        )
        self.headers.update(
            {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            }
        )
        if base_path is None:
            self.base_url = instance_url
        else:
            # Canonicalize base_path
            if base_path[0] == "/":
                base_path = base_path[1:]
            if base_path[-1] != "/":
                base_path += "/"
            self.base_url = urljoin(instance_url, base_path)

    def request(  # type: ignore [override]
        self, method: str | bytes, url: str, *args: Any, **kwargs: Any
    ) -> requests.Response:
        """Potentially rewrite request, relativizing it to self.base_url."""
        # We rely on urllib.parse's urljoin behavior to do the right thing
        # with absolute URLs.
        new_url = urljoin(self.base_url, url)
        return super().request(method, new_url, *args, **kwargs)
