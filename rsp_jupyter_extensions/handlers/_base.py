"""Base RSP-jupyter-extensions handler class."""

from pathlib import Path

from jupyter_server.base.handlers import APIHandler

from ..models.config import FileBrowserRoot
from ._utils import _get_homedir
from .clients import RSPClient
from .config_generator import ConfigGenerator


class _BaseRSPAPIHandler(APIHandler):
    """Base API handler class."""

    def initialize(self) -> None:
        super().initialize()
        cname = self.__class__.__name__
        self._logger = self.log
        if "client" not in self.settings:
            self._logger.info(f"Initializing RSP Client for {cname}")
            self.settings["client"] = RSPClient(logger=self.log)
        self._rsp_client = self.settings["client"]
        self._generator = ConfigGenerator()  # Singleton
        if "rsp_config" not in self.settings:
            self._logger.info(f"Initializing ConfigGenerator for {cname}")
            self.settings["rsp_config"] = self._generator.generate_config()
        self._logger.info(f"Initializing {cname}")

    async def ensure_config(self) -> None:
        await self._generator.update_statusbar()

    async def _get_jupyter_server_root(self) -> Path:
        await self.ensure_config()
        if (
            self.settings["rsp_config"].file_browser_root
            == FileBrowserRoot.ROOT
        ):
            return Path("/")
        # If we don't have a config, or the setting is not ROOT, just
        # hand back the homedir
        return _get_homedir()

    async def _reabsolutize_path(self, path: Path) -> Path:
        if path.is_absolute():
            return path
        # We need to re-absolutize it so it doesn't get written to wherever
        # the Lab extension is running from.  If it is relative, it's relative
        # to the Jupyter Server root, which might be $HOME or might be /.
        root_dir = await self._get_jupyter_server_root()
        return root_dir / path
