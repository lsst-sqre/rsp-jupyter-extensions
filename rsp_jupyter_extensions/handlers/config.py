"""Send baked-in config (mounted as configmap)."""

import json

import tornado
from jupyter_server.base.handlers import APIHandler

from ..constants import CONFIG_FILE


class ConfigHandler(APIHandler):
    """Config handler.  Return the config file contents (already JSON)."""

    def initialize(self) -> None:
        super().initialize()
        self.log.info("Initializing ConfigHandler.")

    @tornado.web.authenticated
    def get(self) -> None:
        """Emit environment to calling HTTP client."""
        self.log.info("Sending Rubin config")
        try:
            self.write(CONFIG_FILE.read_text())
        except (FileNotFoundError, UnicodeDecodeError):
            # We should never actually build a Lab image without the mounted
            # configmap here.  All sorts of things will fail if this isn't
            # sending back a Lab config, but if somehow that happens, we
            # send enough that that Lab should start, albeit with a degraded
            # UI.
            #
            # In practice, the startup container should have failed if we
            # didn't have a config file, so it's unlikely we will get here.
            self.log.warning(
                f"Error reading {CONFIG_FILE!s}; sending fallback default"
            )
            def_cfg = {
                "container_size": "Unknown",
                "debug": False,
                "enable_rubin_query_menu": False,
                "enable_tutorials_menu": True,
                "file_browser_root": "home",
                "home_relative_to_file_browser_root": "",
                "image": {
                    "description": "Unknown",
                    "digest": "sha256:unknown",
                    "spec": "unknown:unknown@sha256:unknown",
                },
                "jupyterlab_config_dir": "/etc/nublado",
                "repertoire_base_url": "https://example.com/repertoire",
                "reset_user_env": False,
                "resources": {
                    "limits": {
                        "cpu": -1,
                        "memory": -1,
                    },
                    "requests": {
                        "cpu": -1,
                        "memory": -1,
                    },
                },
                "runtime_mounts_dir": "/etc/nublado",
            }
            self.write(json.dumps(def_cfg, sort_keys=True, indent=2))
