"""Backend for Gafaelfawr-aware replacement for Hub menu items."""

import os
from typing import Any

import requests
import tornado
from jupyter_server.base.handlers import APIHandler
from jupyter_server.utils import url_path_join as ujoin


class HubHandler(APIHandler):
    """
    Hub Handler.  Currently all we do is DELETE (to shut down a running Lab
    instance) but we could extend this to do anything in the Hub REST API.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def lsstquery(self) -> str:
        return self.settings["lsstquery"]

    @tornado.web.authenticated
    def delete(self) -> None:
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
        if not token:
            self.log.warning("Token unknown; Hub communication impossible.")
            return
        api_url = os.environ.get("JUPYTERHUB_API_URL")
        if not api_url:
            self.log.warning("API URL unknown; Hub communication impossible.")
            return
        endpoint = ujoin(api_url, f"/users/{user}/server")
        # Boom goes the dynamite.
        self.log.info(f"Requesting hub shutdown from {endpoint}")
        headers = {"Authorization": f"token {token}"}
        requests.delete(endpoint, headers=headers, timeout=30)
