"""Convenience endpoint to centralize service discovery."""

import json
from dataclasses import asdict

import tornado

from ._base import _BaseRSPAPIHandler


class ServiceInfoHandler(_BaseRSPAPIHandler):
    """Service Info Handler.  Basically a primer for, and wrapper around, the
    RSP Client.
    """

    @tornado.web.authenticated
    async def get(self) -> None:
        """Emit serviceinfo to calling HTTP client."""
        self.log.debug("Assembling RSP Service Info")
        ep = await self._rsp_client.get_serviceinfo()
        self.log.info("Sending RSP Service Info")
        self.write(json.dumps(asdict(ep), sort_keys=True, indent=2))
