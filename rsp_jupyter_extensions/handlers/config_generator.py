"""Send baked-in config.

Eventually this will probably be mounted as a configmap.  For right now, it
is calculated from the environment, so what we are returning is a sanitized
derived subset of the process environment.  We use the Tornado settings dict
in order to cache the results between handler calls.
"""

import os
from typing import Any, Self

from httpx import AsyncClient
from rubin.repertoire import DiscoveryClient

from ..exceptions import ConfigError
from ..models.config import (
    FileBrowserRoot,
    LabImage,
    LabResource,
    LabResources,
    RSPConfig,
)
from ._utils import _get_homedir


class ConfigGenerator:
    """Config Generator.  This is a singleton.  It uses the environment
    (for now) and will eventually use config.json.
    """

    _instance: None | Self = None

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._config: RSPConfig | None = None
        self._config = self.generate_config()
        _anonymous_client = AsyncClient(
            headers={"Content-Type": "application/json"}
        )
        if self._config is None:
            raise ConfigError("Config could not be determined")
        self._discovery_client = DiscoveryClient(
            _anonymous_client, base_url=self._config.repertoire_base_url
        )

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
        fbr = ConfigGenerator._fbr_from_env()
        if fbr == FileBrowserRoot.HOME:
            return ""
        return str(_get_homedir()).lstrip("/")

    def regenerate_config(self) -> None | RSPConfig:
        self._config = None  # Force config to be empty, so generate runs.
        self.generate_config()
        return self._config

    def generate_config(self) -> None | RSPConfig:
        """Sanitized version of environment.  Note that eventually we want
        to pass this as a separate config.json, and any remaining environment
        variables that we control (i.e. are not set by Jupyter) should be
        namespaced under NUBLADO_* .
        """
        if self._config is not None:
            return self._config
        image = LabImage(
            description=os.environ.get(
                "IMAGE_DESCRIPTION", self._image_spec_to_tag()
            ),
            digest=os.environ.get(
                "IMAGE_DIGEST", self._image_spec_to_digest()
            ),
            spec=os.environ.get("JUPYTER_IMAGE_SPEC", ""),
        )
        # RSP_SITE_TYPE in particular will be replaced soon.
        staff_or_science = bool(
            os.environ.get("RSP_SITE_TYPE") == "science"
        ) or bool(os.environ.get("RSP_SITE_TYPE") == "staff")
        self._config = RSPConfig(
            container_size=os.environ.get("CONTAINER_SIZE", "Unknown"),
            debug=bool(os.environ.get("DEBUG")),
            enable_landing_page=(os.environ.get("RSP_SITE_TYPE") == "science"),
            enable_queries_menu=(
                bool(os.environ.get("ENABLE_RUBIN_QUERY_MENU"))
                or staff_or_science
            ),
            enable_tutorials_menu=(
                bool(os.environ.get("ENABLE_TUTORIALS_MENU"))
                or staff_or_science
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
            statusbar="",  # Populated via async method
            tutorial_notebooks_cache_dir=os.environ.get(
                "TUTORIAL_NOTEBOOKS_CACHE_DIR", ""
            ),
            tutorial_notebooks_url=os.environ.get(
                "TUTORIAL_NOTEBOOKS_URL",
                "https://github.com/lsst/tutorial-notebooks@main",
            ),
        )
        return self._config

    async def update_statusbar(self) -> None:
        if self._config is None:
            raise ConfigError("Config could not be determined")
        if self._config.statusbar:
            return
        descr = self._config.image.description
        spec = self._config.image.spec
        digest = self._config.image.digest
        digest_str = f" [{digest[0:8]}...]"
        img_arr = spec.split("/")
        try:
            pullname, _ = img_arr[-1].split("@", 1)
            imagename = f" ({pullname})"
        except ValueError:
            imagename = ""
        statusbar = descr + digest_str + imagename
        env_name = await self._discovery_client.environment_name()
        if env_name is not None:
            statusbar += " " + env_name
        self._config.statusbar = statusbar
