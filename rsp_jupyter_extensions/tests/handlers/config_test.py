"""Test that environment works with both abnormal and config endpoints."""

import json
from collections.abc import Callable
from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem


async def test_config(
    jp_fetch: Callable,
    rsp_fs: FakeFilesystem,
) -> None:
    """Test `config` endpoint."""
    response = await jp_fetch("rubin", "config")
    assert response.code == 200
    payload = json.loads(response.body)
    assert payload == {
        "collab_dir": "/collab",
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


async def test_config_file(
    labcfg: str,
    jp_fetch: Callable,
    rsp_fs: FakeFilesystem,
) -> None:
    """Test `config` endpoint."""
    cfg = json.loads(labcfg)
    Path("/etc/nublado/config").mkdir()
    Path("/etc/nublado/config/lab-config.json").write_text(labcfg)
    response = await jp_fetch("rubin", "config")
    assert response.code == 200
    payload = json.loads(response.body)
    # Add the calculated-later fields
    cfg["enable_landing_page"] = False
    cfg["statusbar"] = (
        "Experimental Weekly 2026_21 [ai] [89e0fd32...]"
        " (sciplat-lab:exp_w_2026_21_ai) example.lsst.cloud"
    )
    cfg["tutorial_notebooks_cache_dir"] = ""
    cfg["tutorial_notebooks_url"] = (
        "https://github.com/lsst/tutorial-notebooks@main"
    )
    assert payload == cfg
