"""Test that environment works with both abnormal and config endpoints."""

import json
import logging
from collections.abc import Callable
from pathlib import Path

import pytest

from rsp_jupyter_extensions.handlers.config_generator import ConfigGenerator
from rsp_jupyter_extensions.models.config import RSPConfig


async def test_config(
    caplog: pytest.LogCaptureFixture,
    jp_fetch: Callable,
) -> None:
    """Test `config` endpoint."""
    response = await jp_fetch("rubin", "config")
    assert response.code == 200
    payload = json.loads(response.body)
    # Note that collab_dir is set in the config (to "/collab")
    assert payload == {
        "collab_dir": None,
        "container_size": "Large (4.0 CPU, 16Gi RAM)",
        "debug": False,
        "enable_jobs_menu": False,
        "enable_landing_page": False,
        "enable_tutorials_menu": False,
        "file_browser_root": "home",
        "home_relative_to_file_browser_root": "",
        "image": {
            "description": "Daily 2026_03_31",
            "digest": (
                "ae3bfaed76677dc396f0924085481f38d6a2510da"
                "3d03fd5c9710009e50b6f28"
            ),
            "spec": (
                "us-central1-docker.pkg.dev/rubin-shared-services-71ec/"
                "sciplat/sciplat-lab:d_2026_03_31@sha256:ae3bfaed76677"
                "dc396f0924085481f38d6a2510da3d03fd5c9710009e50b6f28"
            ),
        },
        "jupyterlab_config_dir": "/opt/lsst/software/jupyterlab",
        "repertoire_base_url": "https://example.lsst.cloud/repertoire",
        "reset_user_env": False,
        "resources": {
            "limits": {
                "cpu": 4.0,
                "memory": 17179869184,
            },
            "requests": {
                "cpu": 1.0,
                "memory": 4294967296,
            },
        },
        "runtime_mounts_dir": "/etc/nublado",
        "statusbar": (
            "Daily 2026_03_31 [ae3bfaed...] (sciplat-lab:d_2026_03_31) "
            "example.lsst.cloud"
        ),
        "tutorial_notebooks_cache_dir": "",
        "tutorial_notebooks_url": (
            "https://github.com/lsst/tutorial-notebooks@main"
        ),
    }
    messages = [
        x.message
        for x in caplog.get_records("setup")
        if x.levelno == logging.WARNING
    ]
    # Check that "/collab" was unset when the extension loaded and determined
    # it to be missing.
    assert "Collab dir /collab does not exist" in messages


async def test_config_file(
    labcfg: str,
    monkeypatch: pytest.MonkeyPatch,
    rsp_fs: Path,
) -> None:
    """Test loading config from file."""
    cfg = json.loads(labcfg)
    cfg_obj = RSPConfig.model_validate(cfg)

    cfg_path = Path("/etc") / "nublado" / "config" / "lab-config.json"
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text(labcfg)

    cg = ConfigGenerator()
    # Try standard file
    new_cfg_obj = cg.regenerate_config()

    # Copy calculated fields
    for fld in (
        "statusbar",
        "tutorial_notebooks_cache_dir",
        "tutorial_notebooks_url",
    ):
        setattr(cfg_obj, fld, getattr(new_cfg_obj, fld))

    assert new_cfg_obj == cfg_obj
    assert new_cfg_obj.runtime_mounts_dir == "/etc/nublado"
    # Check that collab dir is set since it exists in rsp_fs.
    assert new_cfg_obj.collab_dir == "/collab"

    # Now change config and put somewhere else.

    monkeypatch.setenv("NUBLADO_RUNTIME_MOUNTS_DIR", "/collab")
    cfg_path = Path("/collab") / "config" / "lab-config.json"
    cfg["debug"] = False
    cfg["enable_tutorials"] = False
    cfg["runtime_mounts_dir"] = "/collab"
    cfg_path.parent.mkdir()
    cfg_path.write_text(json.dumps(cfg))

    cfg_obj = RSPConfig.model_validate(cfg)
    cg = ConfigGenerator()
    # Try standard file
    new_cfg_obj = cg.regenerate_config()

    # Copy calculated fields
    for fld in (
        "statusbar",
        "tutorial_notebooks_cache_dir",
        "tutorial_notebooks_url",
    ):
        setattr(cfg_obj, fld, getattr(new_cfg_obj, fld))

    assert new_cfg_obj == cfg_obj
    assert new_cfg_obj.runtime_mounts_dir == "/collab"
