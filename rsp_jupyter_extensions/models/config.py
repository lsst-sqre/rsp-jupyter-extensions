"""Model for RSP Lab container config."""

from __future__ import annotations

from enum import StrEnum, auto

from pydantic import BaseModel

__all__ = [
    "FileBrowserRoot",
    "LabImage",
    "LabResource",
    "LabResources",
    "RSPConfig",
]


class FileBrowserRoot(StrEnum):
    """Possible Values for filebrowser top."""

    HOME = auto()
    ROOT = auto()


class LabImage(BaseModel):
    """Information about running Lab image."""

    description: str
    digest: str
    spec: str


class LabResource(BaseModel):
    """Memory and CPU for running Lab."""

    memory: int  # bytes
    cpu: float  # cores, can be fractional


class LabResources(BaseModel):
    """Limits and Requests for running Lab."""

    limits: LabResource
    requests: LabResource


class RSPConfig(BaseModel):
    """Configuration of RSP Lab container."""

    container_size: str
    collab_dir: str = ""
    debug: bool
    enable_jobs_menu: bool
    enable_landing_page: bool = False
    enable_tutorials_menu: bool
    file_browser_root: FileBrowserRoot
    home_relative_to_file_browser_root: str
    image: LabImage
    jupyterlab_config_dir: str
    repertoire_base_url: str
    reset_user_env: bool
    resources: LabResources
    runtime_mounts_dir: str
    statusbar: str = ""
    tutorial_notebooks_cache_dir: str = ""
    tutorial_notebooks_url: str = ""
