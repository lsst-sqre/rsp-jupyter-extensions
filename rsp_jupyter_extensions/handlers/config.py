"""Send baked-in config.

Eventually this will probably be mounted as a configmap.  For right now, it
is calculated from the environment, so what we are returning is a sanitized
derived subset of the process environment.
"""

import json
import os
from typing import Any

import tornado
from jupyter_server.base.handlers import APIHandler

from ._utils import _get_base_url


class ConfigHandler(APIHandler):
    """Config handler.  Return a subset of the environment."""

    def initialize(self) -> None:
        super().initialize()
        self._convert_environ_to_config()
        self.log.info("Initializing ConfigHandler.")

    @staticmethod
    def _image_spec_to_tag() -> str:
        spec = os.environ.get("JUPYTER_IMAGE_SPEC", "")
        if not spec:
            return ""
        try:
            _, rest = spec.split(":")
            tag, _ = rest.split("@")
        except ValueError:
            return ""
        return tag

    @staticmethod
    def _image_spec_to_digest() -> str:
        spec = os.environ.get("JUPYTER_IMAGE_SPEC", "")
        if not spec:
            return ""
        try:
            _, sha_digest = spec.split("@")
            _, digest = sha_digest.split(":")
        except ValueError:
            return ""
        return digest

    def _convert_environ_to_config(self) -> None:
        """Sanitized version of environment.  Note that eventually we want
        to pass this as a separate config.json, and any remaining environment
        variables should be namespaced under NUBLADO_* .

        Once we have config.json, we will proceed by updating self._cfg from
        it, and then eventually dropping the environment settings parsing
        entirely.
        """
        self._cfg: dict[str, Any] = {
            "container_size": os.environ.get("CONTAINER_SIZE", "Unknown"),
            "debug": bool(os.environ.get("DEBUG")),
            "enable_landing_page": (
                os.environ.get("RSP_SITE_TYPE") == "science"
            ),
            "enable_queries_menu": bool(
                os.environ.get("ENABLE_RUBIN_QUERY_MENU")
            ),
            "enable_tutorials_menu": bool(
                os.environ.get("ENABLE_TUTORIALS_MENU")
            ),
            "file_browser_root": os.environ.get("FILE_BROWSER_ROOT", "home"),
            "home_relative_to_file_browser_root": os.environ.get(
                "HOME_RELATIVE_TO_FILE_BROWSER_ROOT", ""
            ),
            "image": {
                "description": os.environ.get(
                    "IMAGE_DESCRIPTION", self._image_spec_to_tag()
                ),
                "digest": os.environ.get(
                    "IMAGE_DIGEST", self._image_spec_to_digest()
                ),
                "spec": os.environ.get("JUPYTER_IMAGE_SPEC", ""),
            },
            "jupyterlab_config_dir": os.environ.get(
                "JUPYTERLAB_CONFIG_DIR", ""
            ),
            "repertoire_base_url": os.environ.get("REPERTOIRE_BASE_URL", ""),
            "reset_user_env": bool(os.environ.get("RESET_USER_ENV")),
            "resources": {
                "limits": {
                    "cpu": float(os.environ.get("CPU_LIMIT", "-1")),
                    "memory": int(os.environ.get("MEM_LIMIT", "-1")),
                },
                "requests": {
                    "cpu": float(os.environ.get("CPU_GUARANTEE", "-1")),
                    "memory": int(os.environ.get("MEM_GUARANTEE", "-1")),
                },
            },
            "runtime_mounts_dir": os.environ.get(
                "NUBLADO_RUNTIME_MOUNTS_DIR", ""
            ),
        }
        # Fixup until we eliminate RSP_SITE_TYPE (requires Nublado changes)
        rsp_site_type = os.environ.get("RSP_SITE_TYPE", "")
        if rsp_site_type in ("staff", "science"):
            self._cfg["enable_tutorials_menu"] = True
        if rsp_site_type == "science":
            self._cfg["enable_queries_menu"] = True
        # Fixup until we change this to use config.json and service
        # discovery.
        self._cfg["statusbar"] = self._get_statusbar()

    def _get_statusbar(self) -> str:
        descr = self._cfg["image"]["description"]
        spec = self._cfg["image"]["spec"]
        digest = self._cfg["image"]["digest"]
        digest_str = f" [{digest[0:8]}...]"
        img_arr = spec.split("/")
        try:
            pullname, _ = img_arr[-1].split("@", 1)
            imagename = f" ({pullname})"
        except ValueError:
            imagename = ""
        # Fixup until we have service discovery
        base_url = f" {_get_base_url()}"
        return descr + digest_str + imagename + base_url

    @tornado.web.authenticated
    def get(self) -> None:
        """Emit config to calling HTTP client."""
        self.log.info("Sending Rubin config")
        self.write(json.dumps(self._cfg, sort_keys=True, indent=2))
