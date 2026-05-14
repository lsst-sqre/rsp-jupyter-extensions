"""Backend for Gafaelfawr-aware replacement for Hub menu items."""

import os

import tornado
from httpx import AsyncClient
from jupyter_server.utils import url_path_join as ujoin

from ._base import _BaseRSPAPIHandler


class HubHandler(_BaseRSPAPIHandler):
    """
    Hub Handler.  Currently all we do is DELETE (to shut down a running Lab
    instance) but we could extend this to do anything in the Hub REST API.
    """

    @tornado.web.authenticated
    async def delete(self) -> None:
        """
        Send a DELETE to the Hub API, which will result in this Lab
        instance being terminated (potentially, along with its namespace).

        We will need to make this more clever when and if we have multiple
        named servers.
        """
        user = os.environ.get("JUPYTERHUB_USER")
        if not user:
            self.log.warning("User unknown; Hub communication impossible.")
            return
        token = os.environ.get("JUPYTERHUB_API_TOKEN")
        # We want the JupyterHub comm token, *not* the Gafaelfawr access
        # token.
        if not token:
            self.log.warning(
                "Hub token unknown; Hub communication impossible."
            )
            return
        api_url = os.environ.get("JUPYTERHUB_API_URL")
        if not api_url:
            self.log.warning("API URL unknown; Hub communication impossible.")
            return
        # This would have to be smarter if we had multiple servers.
        endpoint = ujoin(api_url, f"/users/{user}/server")
        # Boom goes the dynamite.
        self.log.info(f"Requesting hub shutdown from {endpoint}")
        headers = {
            "Authorization": f"token {token}",
            "Content-Type": "application/json",
        }
        client = AsyncClient(headers=headers)
        await client.delete(endpoint, headers=headers, timeout=30)
