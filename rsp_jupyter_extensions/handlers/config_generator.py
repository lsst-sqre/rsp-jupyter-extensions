"""Send baked-in config.

If this is mounted into the container, use that version (augmented with
statusbar (calculated asynchronously) and tutorial cache information).

If not, calculate it from the environment.

We use the Tornado settings dict to cache results between handler calls.
"""

import json
import logging
import os
from pathlib import Path
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
            # If it's been initialized, it will also have a logger.
            self._logger.debug(  # type:ignore[has-type]
                "Config generator already created"
            )
            return
        self._initialized = True
        self._logger = logging.getLogger(__name__)
        self._logger.debug("Config generator initializing")
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
        self._logger.info("Config generator initialized")

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

    def regenerate_config(self) -> RSPConfig:
        """Force regeneration of config.

        Returns
        -------
        RSPConfig|None
            Lab configuration.
        """
        self._config = None  # Force config to be empty, so generate must run.
        return self.generate_config()

    def generate_config(self) -> RSPConfig:
        """Generate Lab configuration.  Check first for a mounted configuration
        file and use that if it exists; otherwise, use a sanitized version of
        the environment.

        Returns
        -------
        RSPConfig|None
            Lab configuration.
        """
        self._logger.debug("Generating config")
        if self._config is not None:
            self._logger.debug("Returning cached config")
            return self._config
        cfg_file = (
            Path(os.getenv("NUBLADO_RUNTIME_MOUNTS_DIR", "/etc/nublado"))
            / "config"
            / "lab-config.json"
        )
        self._logger.debug(f"Searching for config file at {cfg_file!s}")
        if cfg_file.exists():
            cf = self._load_config_file(cfg_file)
            if cf:
                self._config = cf
                self._logger.debug(f"Loaded config from {cfg_file!s}")
                self._check_collab_config()
                return cf
            self._logger.warning(f"Failed to load config from {cfg_file!s}")
        else:
            self._logger.warning(f"{cfg_file!s} does not exist")
        self._logger.warning("Falling back to environment-based config")
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
            collab_dir=os.environ.get("NUBLADO_COLLAB_DIR"),
            container_size=os.environ.get("CONTAINER_SIZE", "Unknown"),
            debug=bool(os.environ.get("DEBUG")),
            enable_jobs_menu=(
                bool(os.environ.get("ENABLE_RUBIN_QUERY_MENU"))
                or staff_or_science
            ),
            enable_landing_page=(os.environ.get("RSP_SITE_TYPE") == "science"),
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
        self._check_collab_config()
        return self._config

    def _check_collab_config(self) -> None:
        cfg = self._config
        if not cfg:  # Placate mypy.  We will certainly have it before now.
            return
        collab_dir = cfg.collab_dir
        if collab_dir:
            collab_path = Path(collab_dir)
            if collab_path.exists():
                if collab_path.is_dir():
                    self._logger.debug(
                        f"Collab dir {collab_dir} exists and is directory"
                    )
                    return
                else:
                    self._logger.warning(
                        f"Collab dir {collab_dir} exists but is not directory"
                    )
            else:
                self._logger.warning(f"Collab dir {collab_dir} does not exist")
            cfg.collab_dir = None

    def _load_config_file(self, cfg_file: Path) -> RSPConfig | None:
        rspcfg: RSPConfig | None = None
        try:
            obj = json.loads(cfg_file.read_text())
            obj["enable_landing_page"] = (
                os.environ.get("RSP_SITE_TYPE") == "science"
            )
            obj["tutorial_notebooks_cache_dir"] = os.environ.get(
                "TUTORIAL_NOTEBOOKS_CACHE_DIR", ""
            )
            obj["tutorial_notebooks_url"] = os.environ.get(
                "TUTORIAL_NOTEBOOKS_URL",
                "https://github.com/lsst/tutorial-notebooks@main",
            )
            rspcfg = RSPConfig.model_validate(obj)
        except Exception:
            self._logger.exception(f"Loading config file {cfg_file!s} failed")
        return rspcfg

    async def update_statusbar(self) -> None:
        if self._config is None:
            raise ConfigError("Config could not be determined")
        if self._config.statusbar:
            return
        descr = self._config.image.description
        spec = self._config.image.spec
        digest = self._config.image.digest
        if digest.find(":") > -1:
            # Throw away method (e.g. sha256:0942... -> 0942...)
            digest = digest.split(":", 2)[1]
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
