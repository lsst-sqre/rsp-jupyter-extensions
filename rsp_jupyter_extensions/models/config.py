"""Model for RSP Lab container config."""

from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "FileBrowserRoot",
    "LabImage",
    "LabResource",
    "LabResources",
    "RSPConfig",
]


class FileBrowserRoot(StrEnum):
    """Possible Values for filebrowser top."""

    HOME = "home"
    ROOT = "root"


@dataclass
class LabImage:
    """Information about running Lab image."""

    description: str
    digest: str
    spec: str


@dataclass
class LabResource:
    """Memory and CPU for running Lab."""

    memory: int  # bytes
    cpu: float  # cores, can be fractional


@dataclass
class LabResources:
    """Limits and Requests for running Lab."""

    limits: LabResource
    requests: LabResource


@dataclass
class RSPConfig:
    """Configuration of RSP Lab container."""

    container_size: str
    debug: bool
    enable_landing_page: bool
    enable_queries_menu: bool
    enable_tutorials_menu: bool
    file_browser_root: FileBrowserRoot
    home_relative_to_file_browser_root: str
    image: LabImage
    jupyterlab_config_dir: str
    repertoire_base_url: str
    reset_user_env: bool
    resources: LabResources
    runtime_mounts_dir: str
    statusbar: str
