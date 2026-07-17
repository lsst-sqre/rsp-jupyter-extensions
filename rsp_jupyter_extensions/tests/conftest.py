"""Fixture for test suite."""
import os
from pathlib import Path
from typing import Iterator

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem
import respx

from rubin.repertoire import Discovery, register_mock_discovery
from rsp_jupyter_extensions.handlers.config_generator import ConfigGenerator

@pytest.fixture(autouse=True)
def reset_config_instance() -> None:
    """Reset ConfigGenerator -- in actual operation it's a singleton, but
    we want to reset it for each test."""
    cg = ConfigGenerator()
    if hasattr(cg, "_initialized"):
        del cg._initialized


@pytest.fixture(autouse=True)
def rsp_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Environment variables for an RSP instance, used to populate config."""
    with monkeypatch.context() as mc:
        mc.setenv("CONTAINER_SIZE", "Large (4.0 CPU, 16Gi RAM)")
        mc.setenv("IMAGE_DESCRIPTION", "Daily 2026_03_31")
        mc.setenv(
        "IMAGE_DIGEST",
        ("ae3bfaed76677dc396f0924085481f38d6a2510da3d03fd5c9710009e50b6f28"),
    )
        mc.setenv(
        "JUPYTER_IMAGE_SPEC",
        (
            "us-central1-docker.pkg.dev/rubin-shared-services-71ec/sciplat/"
            "sciplat-lab:d_2026_03_31@sha256:"
            "ae3bfaed76677dc396f0924085481f38d6a2510da3d03fd5c9710009e50b6f28"
        ),
    )
        mc.setenv(
        "JUPYTERLAB_CONFIG_DIR", "/opt/lsst/software/jupyterlab"
    )
        mc.setenv("NUBLADO_RUNTIME_MOUNTS_DIR", "/etc/nublado")
        mc.setenv("CPU_LIMIT", "4.0")
        mc.setenv("CPU_GUARANTEE", "1.0")
        mc.setenv("MEM_LIMIT", "17179869184")
        mc.setenv("MEM_GUARANTEE", "4294967296")
        mc.setenv("JUPYTERHUB_HOST", "https://nb.example.lsst.cloud")
        yield

@pytest.fixture(autouse=True)
def mock_discovery(
    respx_mock: respx.Router, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Discovery]:
    """Mock out service discovery."""
    with monkeypatch.context() as mc:
        mc.setenv("REPERTOIRE_BASE_URL",
                           "https://example.lsst.cloud/repertoire")
        path = (Path(__file__).parent / "data" / "etc" / "nublado"
                / "discovery_v1.json")
        yield register_mock_discovery(respx_mock, path)

def _add_real_directory(
    fs:FakeFilesystem,
    pathname: str
) -> None:
    datadir = Path(__file__).parent / "data"
    fs.add_real_directory(
        datadir / pathname,
        target_path = f"/{pathname}",
    )

@pytest.fixture
def rsp_fs(
    fs: FakeFilesystem,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[FakeFilesystem]:
    """Simulate enough of an RSP filesystem to run tests."""
    for dd in ("etc", "home", "collab"):
        _add_real_directory(fs, dd)
    with monkeypatch.context() as mc:
        mc.setenv("HOME", "/home/irian")
        env_p=os.getenv("PATH", "/bin:/usr/bin")
        env_p=f"/usr/local/bin:{env_p}"
        mc.setenv("PATH", env_p)
        yield fs

@pytest.fixture
def tutorial_env(tmp_path:Path) -> Path:
    """Environment for tutorial tests; pyfakefs doesn't work here
    because setting up the handler internally uses subprocess and the
    in-memory fake filesystem doesn't persist across the spawned
    process.
    """
    # Set up test files
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "subsubdir").mkdir()
    for p in (
        tmp_path,
        tmp_path / "subdir",
        tmp_path / "subdir" / "subsubdir",
    ):
        (p / "hello.txt").write_text("Hello, world!\n")
        (p / "hello.py").write_text("print('Hello, world!')\n")
    # Create .git directory so we don't pull the repo.
    (tmp_path / ".git").mkdir()

    return tmp_path

@pytest.fixture
def labcfg() -> str:
    return (
        Path(__file__).parent / "data" / "config" / "lab-config.json"
    ).read_text()
