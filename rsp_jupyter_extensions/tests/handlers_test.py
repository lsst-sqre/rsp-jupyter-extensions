"""Test that environment works with both abnormal and config endpoints."""

import json
from collections.abc import Callable

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem


async def test_abnormal(
    jp_fetch: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    # When
    monkeypatch.setenv("TEST_KEY", "test_value")
    response = await jp_fetch("rubin", "abnormal")

    # Then
    assert response.code == 200
    payload = json.loads(response.body)
    assert payload == {}

    monkeypatch.setenv("ABNORMAL_STARTUP", "TRUE")
    response = await jp_fetch("rubin", "abnormal")
    assert response.code == 200
    payload = json.loads(response.body)
    assert payload["ABNORMAL_STARTUP"] == "TRUE"


async def test_config(
    jp_fetch: Callable, rsp_fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test `config` endpoint."""
    monkeypatch.setenv("CONTAINER_SIZE", "Large (4.0 CPU, 16Gi RAM)")
    monkeypatch.setenv("IMAGE_DESCRIPTION", "Daily 2026_03_31")
    monkeypatch.setenv(
        "IMAGE_DIGEST",
        ("ae3bfaed76677dc396f0924085481f38d6a2510da3d03fd5c9710009e50b6f28"),
    )
    monkeypatch.setenv(
        "JUPYTER_IMAGE_SPEC",
        (
            "us-central1-docker.pkg.dev/rubin-shared-services-71ec/sciplat/"
            "sciplat-lab:d_2026_03_31@sha256:"
            "ae3bfaed76677dc396f0924085481f38d6a2510da3d03fd5c9710009e50b6f28"
        ),
    )
    monkeypatch.setenv(
        "JUPYTERLAB_CONFIG_DIR", "/opt/lsst/software/jupyterlab"
    )
    monkeypatch.setenv(
        "NUBLADO_RUNTIME_MOUNTS_DIR", "/opt/lsst/software/jupyterlab"
    )
    monkeypatch.setenv(
        "REPERTOIRE_BASE_URL", "https://example.lsst.cloud/repertoire"
    )
    monkeypatch.setenv("CPU_LIMIT", "4.0")
    monkeypatch.setenv("CPU_GUARANTEE", "1.0")
    monkeypatch.setenv("MEM_LIMIT", "17179869184")
    monkeypatch.setenv("MEM_GUARANTEE", "4294967296")
    monkeypatch.setenv("JUPYTERHUB_HOST", "https://nb.example.lsst.cloud")
    response = await jp_fetch("rubin", "config")
    assert response.code == 200
    payload = json.loads(response.body)
    assert payload == {
        "container_size": "Large (4.0 CPU, 16Gi RAM)",
        "debug": False,
        "enable_rubin_query_menu": False,
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
        "runtime_mounts_dir": "/opt/lsst/software/jupyterlab",
        "statusbar": (
            "Daily 2026_03_31 [ae3bfae...] (sciplat-lab:d_2026_03_31) "
            "https://example.lsst.cloud"
        ),
    }
