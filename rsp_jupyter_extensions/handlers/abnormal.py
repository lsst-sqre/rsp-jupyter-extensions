"""Report any environment variables starting with ABNORMAL_STARTUP."""

import json
import os

import tornado

from ._base import _BaseRSPAPIHandler


class AbnormalStartupHandler(_BaseRSPAPIHandler):
    """
    Abnormal Startup Handler.  If any environment variables beginning with
    ABNORMAL_STARTUP are found, return them as JSON where the key is the
    variable name and the value is its value.
    """

    @tornado.web.authenticated
    def get(self) -> None:
        """Emit Abnormal Startup information to calling HTTP client."""
        self.log.info("Sending Abnormal Startup information")
        self.write(json.dumps(self._get_abnormal(), sort_keys=True, indent=2))

    def _get_abnormal(self) -> dict[str, str]:
        abn = {
            x: os.environ[x]
            for x in [
                y for y in os.environ if y.startswith("ABNORMAL_STARTUP")
            ]
        }
        if abn:
            abn["NB_HOME"] = os.environ.get("NB_HOME", "")
        return abn
