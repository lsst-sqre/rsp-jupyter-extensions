"""Test execution handler functionality."""

from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock

import pytest


async def test_execution_handler_remove_site_packages(
    jp_fetch: Callable,
    mock_nbformat_reads: MagicMock,
    mock_executor: tuple[MagicMock, MagicMock],
    mock_exporter: tuple[MagicMock, MagicMock],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Set up environment
    homedir = tmp_path / "home" / "irian"
    homedir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(homedir))
    tdir = homedir / ".local" / "lib"
    for pver in ["3.8", "3.13"]:
        sp = tdir / f"python{pver}" / "site-packages"
        sp.mkdir(parents=True)
    pdirs = list(tdir.glob("python*/site-packages/"))
    assert len(pdirs) == 2

    _, executor_instance = mock_executor
    # Set up the mock to simulate successful execution
    executor_instance.preprocess.return_value = None

    notebook_str = (
        '{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}'
    )

    response = await jp_fetch(
        "rubin",
        "execution",
        method="POST",
        body=notebook_str,
        params={"kernel_name": "python3"},
    )

    assert response.code == 200
    pdirs = list(tdir.glob("python*/site-packages/"))
    assert len(pdirs) == 2

    # Now retry, specifying the parameter but not the right value

    response = await jp_fetch(
        "rubin",
        "execution",
        method="POST",
        body=notebook_str,
        params={
            "kernel_name": "python3",
            "clear_local_site_packages": "floof",
        },
    )

    assert response.code == 200
    pdirs = list(tdir.glob("python*/site-packages/"))
    assert len(pdirs) == 2

    # Retry with the param set to "false"
    response = await jp_fetch(
        "rubin",
        "execution",
        method="POST",
        body=notebook_str,
        params={
            "kernel_name": "python3",
            "clear_local_site_packages": "false",
        },
    )

    assert response.code == 200
    pdirs = list(tdir.glob("python*/site-packages/"))
    assert len(pdirs) == 2

    # Try again only this time, remove the directories
    response = await jp_fetch(
        "rubin",
        "execution",
        method="POST",
        body=notebook_str,
        params={
            "kernel_name": "python3",
            "clear_local_site_packages": "TrUe",
        },
    )

    assert response.code == 200
    pdirs = list(tdir.glob("python*/site-packages/"))
    assert len(pdirs) == 0
