"""Send baked-in config.

Eventually this will probably be mounted as a configmap.  For right now, it
is calculated from the environment, so what we are returning is a sanitized
derived subset of the process environment.  We use the Tornado settings dict
in order to cache the results between handler calls.
"""

import json

import tornado

from ..models.config import RSPConfig
from ._base import _BaseRSPAPIHandler


class ConfigHandler(_BaseRSPAPIHandler):
    """Config handler.  Return a subset of the environment."""

    async def get_config(self) -> RSPConfig | None:
        """Retrieve config.

        Returns
        -------
        RSPConfig | None
            Configuration settings the front end cares about.
        """
        await self._generator.update_statusbar()
        return self.settings["rsp_config"]

    @tornado.web.authenticated
    async def get(self) -> None:
        """Emit config to calling HTTP client."""
        await self.get_config()
        self.log.info("Sending Rubin config")
        if (
            "rsp_config" not in self.settings
            or self.settings["rsp_config"] is None
        ):
            self.write("{}")
        else:
            self.write(
                json.dumps(
                    self.settings["rsp_config"].model_dump(),
                    sort_keys=True,
                    indent=2,
                )
            )
