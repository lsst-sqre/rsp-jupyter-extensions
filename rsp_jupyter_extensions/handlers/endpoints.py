"""Convenience endpoint to centralize service discovery."""

import json
from dataclasses import asdict

import tornado
from jupyter_server.base.handlers import APIHandler

from ..models.endpoints import Endpoints
from .clients import RSPClient


class EndpointsHandler(APIHandler):
    """Endpoints Handler.  Basically a primer for, and wrapper around, the
    RSP Client.
    """

    def initialize(self) -> None:
        super().initialize()
        if "client" not in self.settings:
            self.settings["client"] = RSPClient(logger=self.log)
        self._rsp_client = self.settings["client"]
        self._endpoints: Endpoints | None = None
        self.log.info("Initializing EndpointsHandler.")

    @tornado.web.authenticated
    async def get(self) -> None:
        """Emit endpoints to calling HTTP client."""
        self.log.debug("Assembling RSP Endpoints")
        ep = await self._rsp_client.get_endpoints()
        self.log.info("Sending RSP Endpoints")
        self.write(json.dumps(asdict(ep), sort_keys=True, indent=2))
