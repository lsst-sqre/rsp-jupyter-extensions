"""Convenience endpoint to centralize service discovery."""

import json
from dataclasses import asdict

import tornado
from jupyter_server.base.handlers import APIHandler

from .clients import RSPClient


class ServiceInfoHandler(APIHandler):
    """Service Info Handler.  Basically a primer for, and wrapper around, the
    RSP Client.
    """

    def initialize(self) -> None:
        super().initialize()
        if "client" not in self.settings:
            self.settings["client"] = RSPClient(logger=self.log)
        self._rsp_client = self.settings["client"]
        self.log.info("Initializing ServiceInfoHandler.")

    @tornado.web.authenticated
    async def get(self) -> None:
        """Emit serviceinfo to calling HTTP client."""
        self.log.debug("Assembling RSP Service Info")
        ep = await self._rsp_client.get_serviceinfo()
        self.log.info("Sending RSP Service Info")
        self.write(json.dumps(asdict(ep), sort_keys=True, indent=2))
