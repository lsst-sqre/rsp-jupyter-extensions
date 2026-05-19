"""Test execution handler functionality."""

import logging
import shutil
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# @pytest.mark.filterwarnings doesn't suppress warning output.
# Neither does capsys.
async def test_execution_handler_rmtree_error(
    jp_fetch: Callable,
    mock_nbformat_reads: MagicMock,
    mock_executor: tuple[MagicMock, MagicMock],
    mock_exporter: tuple[MagicMock, MagicMock],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Set up environment
    homedir = tmp_path / "home" / "irian"
    homedir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(homedir))
    sitep = homedir / ".local" / "lib" / "python3.13" / "site-packages"
    sitep.mkdir(parents=True)
    (sitep / "good").mkdir()
    (sitep / "bad").mkdir()
    (sitep / "good" / "good").touch()
    (sitep / "bad" / "bad").touch()
    # Make "bad" unwriteable.
    # Note that we have to have a directory with no write bit, because
    # unlinking a file requires write on the file's directory, not on
    # the file itself.
    (sitep / "bad" / "bad").chmod(0o400)
    (sitep / "bad").chmod(0o500)
    spfiles = list(sitep.glob("**/*"))
    assert len(spfiles) == 4

    _, executor_instance = mock_executor
    # Set up the mock to simulate successful execution
    executor_instance.preprocess.return_value = None

    notebook_str = (
        '{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}'
    )

    with caplog.at_level(logging.WARNING):
        response = await jp_fetch(
            "rubin",
            "execution",
            method="POST",
            body=notebook_str,
            params={
                "kernel_name": "python3",
                "clear_local_site_packages": "True",
            },
        )

    assert response.code == 200
    assert "Permission denied: 'bad'" in caplog.text

    # Clean up; not sure all OSes will be sufficiently violent about
    # tempdirs with weird permissions.
    (sitep / "bad").chmod(mode=0o755)
    (sitep / "bad" / "bad").chmod(mode=0o644)
    shutil.rmtree(sitep)
