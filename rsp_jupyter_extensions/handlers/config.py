"""Send baked-in config.

Eventually this will probably be mounted as a configmap.  For right now, it
is calculated from the environment, so what we are returning is a sanitized
derived subset of the process environment.
"""

import json
import os
from dataclasses import asdict

import tornado
from jupyter_server.base.handlers import APIHandler

from ..models.config import (
    FileBrowserRoot,
    LabImage,
    LabResource,
    LabResources,
    RSPConfig,
)
from .clients import RSPClient


class ConfigHandler(APIHandler):
    """Config handler.  Return a subset of the environment."""

    def initialize(self) -> None:
        super().initialize()
        if "client" not in self.settings:
            self.settings["client"] = RSPClient(logger=self.log)
        self._rsp_client = self.settings["client"]
        self._cfg: RSPConfig | None = None
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

    @staticmethod
    def _fbr_from_env() -> FileBrowserRoot:
        fbr = os.environ.get("FILE_BROWSER_ROOT", "home")
        if fbr == "home":
            return FileBrowserRoot.HOME
        elif fbr == "root":
            return FileBrowserRoot.ROOT
        raise RuntimeError(
            "FILE_BROWSER_ROOT, if set, must be 'home' or 'root'"
        )

    @staticmethod
    def _home_relative_to_filebrowser_root() -> str:
        fbr = ConfigHandler._fbr_from_env()
        if fbr == FileBrowserRoot.HOME:
            return ""
        return os.getenv("HOME", "").lstrip("/")

    async def _get_statusbar(self, lab_image: LabImage) -> str:
        descr = lab_image.description
        spec = lab_image.spec
        digest = lab_image.digest
        digest_str = f" [{digest[0:8]}...]"
        img_arr = spec.split("/")
        try:
            pullname, _ = img_arr[-1].split("@", 1)
            imagename = f" ({pullname})"
        except ValueError:
            imagename = ""
        env_name = await self._rsp_client.get_environment_name()
        return descr + digest_str + imagename + " " + env_name

    async def _convert_environ_to_config(self) -> None:
        """Sanitized version of environment.  Note that eventually we want
        to pass this as a separate config.json, and any remaining environment
        variables should be namespaced under NUBLADO_* .

        Once we have config.json, we will proceed by updating self._cfg from
        it, and then eventually dropping the environment settings parsing
        entirely.
        """
        if self._cfg is not None:
            return
        image = LabImage(
            description=os.environ.get(
                "IMAGE_DESCRIPTION", self._image_spec_to_tag()
            ),
            digest=os.environ.get(
                "IMAGE_DIGEST", self._image_spec_to_digest()
            ),
            spec=os.environ.get("JUPYTER_IMAGE_SPEC", ""),
        )
        self._cfg = RSPConfig(
            container_size=os.environ.get("CONTAINER_SIZE", "Unknown"),
            debug=bool(os.environ.get("DEBUG")),
            enable_landing_page=(os.environ.get("RSP_SITE_TYPE") == "science"),
            enable_queries_menu=bool(
                os.environ.get("ENABLE_RUBIN_QUERY_MENU")
            ),
            enable_tutorials_menu=bool(
                os.environ.get("ENABLE_TUTORIALS_MENU")
            ),
            file_browser_root=self._fbr_from_env(),
            home_relative_to_file_browser_root=(
                self._home_relative_to_filebrowser_root()
            ),
            image=image,
            jupyterlab_config_dir=os.environ.get("JUPYTERLAB_CONFIG_DIR", ""),
            repertoire_base_url=os.environ.get("REPERTOIRE_BASE_URL", ""),
            reset_user_env=bool(os.environ.get("RESET_USER_ENV")),
            resources=LabResources(
                limits=LabResource(
                    cpu=float(os.environ.get("CPU_LIMIT", "-1")),
                    memory=int(os.environ.get("MEM_LIMIT", "-1")),
                ),
                requests=LabResource(
                    cpu=float(os.environ.get("CPU_GUARANTEE", "-1")),
                    memory=int(os.environ.get("MEM_GUARANTEE", "-1")),
                ),
            ),
            runtime_mounts_dir=os.environ.get(
                "NUBLADO_RUNTIME_MOUNTS_DIR", ""
            ),
            statusbar=await self._get_statusbar(image),
        )

    @tornado.web.authenticated
    async def get(self) -> None:
        """Emit config to calling HTTP client."""
        self.log.debug("Assembling Rubin config")
        await self._convert_environ_to_config()
        self.log.info("Sending Rubin config")
        if self._cfg is None:
            self.write("{}")
        else:
            self.write(json.dumps(asdict(self._cfg), sort_keys=True, indent=2))
