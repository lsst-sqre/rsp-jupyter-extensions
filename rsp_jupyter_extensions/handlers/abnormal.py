"""Report any environment variables starting with ABNORMAL_STARTUP."""

import json
import os

import tornado
from jupyter_server.base.handlers import APIHandler


class AbnormalStartupHandler(APIHandler):
    """
    Abnormal Startup Handler.  If any environment variables beginning with
    ABNORMAL_STARTUP are found, return them as JSON where the key is the
    variable name and the value is its value.
    """

    def initialize(self) -> None:
        super().initialize()
        self.log.info("Initializing AbnormalStartupHandler")

    @tornado.web.authenticated
    def get(self) -> None:
        """Emit Abnormal Startup information to calling HTTP client."""
        self.log.info("Sending Abnormal Startup information")
        self.write(json.dumps(self._get_abnormal(), sort_keys=True, indent=2))

    def _get_abnormal(self) -> dict[str, str]:
        return {
            x: os.environ[x]
            for x in [
                y for y in os.environ if y.startswith("ABNORMAL_STARTUP")
            ]
        }
