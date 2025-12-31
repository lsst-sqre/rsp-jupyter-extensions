"""Test execution handler functionality."""

import json
import logging
import shutil
from collections.abc import Callable, Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from nbconvert.preprocessors import CellExecutionError


@pytest.fixture
def mock_nbformat_reads() -> Generator[MagicMock, None, None]:
    """Mock the nbformat.reads function."""
    with patch("nbformat.reads") as mock:
        notebook = MagicMock()
        mock.return_value = notebook
        yield mock


@pytest.fixture
def mock_executor() -> Generator[tuple[MagicMock, MagicMock], None, None]:
    """Mock the ExecutePreprocessor class."""
    with patch("nbconvert.preprocessors.ExecutePreprocessor") as mock:
        executor_instance = MagicMock()
        mock.return_value = executor_instance
        yield mock, executor_instance


@pytest.fixture
def mock_exporter() -> Generator[tuple[MagicMock, MagicMock], None, None]:
    """Mock the NotebookExporter class."""
    with patch("nbconvert.exporters.NotebookExporter") as mock:
        exporter_instance = MagicMock()
        # Return a tuple of (rendered notebook, resources) when
        # from_notebook_node is called
        exporter_instance.from_notebook_node.return_value = (
            "notebook-content",
            {},
        )
        mock.return_value = exporter_instance
        yield mock, exporter_instance


async def test_execution_handler_post_success(
    jp_fetch: Callable,
    mock_nbformat_reads: MagicMock,
    mock_executor: tuple[MagicMock, MagicMock],
    mock_exporter: tuple[MagicMock, MagicMock],
) -> None:
    """Test the ExecutionHandler.post method with successful execution."""
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
        headers={"X-Kernel-Name": "python3"},
    )

    assert response.code == 200
    response_data = json.loads(response.body)
    assert "notebook" in response_data
    assert "resources" in response_data
    assert response_data["error"] is None
    mock_nbformat_reads.assert_called_once()
    executor_instance.preprocess.assert_called_once()
    mock_class, _ = mock_executor
    mock_class.assert_called_once_with(kernel_name="python3")


async def test_execution_handler_post_with_resources(
    jp_fetch: Callable,
    mock_nbformat_reads: MagicMock,
    mock_executor: tuple[MagicMock, MagicMock],
    mock_exporter: tuple[MagicMock, MagicMock],
) -> None:
    """Test the ExecutionHandler.post method with notebook and resources."""
    _, executor_instance = mock_executor

    executor_instance.preprocess.return_value = None

    request_body = {
        "notebook": (
            '{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}'
        ),
        "resources": {"metadata": {"path": "/path/to/notebook"}},
    }

    response = await jp_fetch(
        "rubin",
        "execution",
        method="POST",
        body=json.dumps(request_body),
        headers={"X-Kernel-Name": "python3"},
    )

    assert response.code == 200
    response_data = json.loads(response.body)
    assert "notebook" in response_data
    assert "resources" in response_data
    assert response_data["error"] is None

    # Verify method calls with resources
    mock_nbformat_reads.assert_called_once()
    executor_instance.preprocess.assert_called_once()


async def test_execution_handler_post_execution_error(
    jp_fetch: Callable,
    mock_nbformat_reads: MagicMock,
    mock_executor: tuple[MagicMock, MagicMock],
    mock_exporter: tuple[MagicMock, MagicMock],
) -> None:
    """Test the ExecutionHandler.post method with execution error."""
    _, executor_instance = mock_executor
    _, exporter_instance = mock_exporter

    # Set up the execution error with required parameters
    execution_error = CellExecutionError(
        traceback="Error traceback",
        ename="RuntimeError",
        evalue="Execution failed",
    )

    executor_instance.preprocess.side_effect = execution_error

    executor_instance.nb = MagicMock()
    executor_instance.resources = MagicMock()

    notebook_str = (
        '{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}'
    )

    response = await jp_fetch(
        "rubin",
        "execution",
        method="POST",
        body=notebook_str,
        headers={"X-Kernel-Name": "python3"},
    )

    assert response.code == 200
    response_data = json.loads(response.body)
    assert "notebook" in response_data
    assert "resources" in response_data
    assert response_data["error"] is not None
    assert response_data["error"]["traceback"] == "Error traceback"
    assert response_data["error"]["ename"] == "RuntimeError"
    assert response_data["error"]["evalue"] == "Execution failed"

    mock_nbformat_reads.assert_called_once()
    executor_instance.preprocess.assert_called_once()
    exporter_instance.from_notebook_node.assert_called_once_with(
        executor_instance.nb, resources=executor_instance.resources
    )


async def test_execution_handler_post_generic_error(
    jp_fetch: Callable,
    mock_nbformat_reads: MagicMock,
    mock_executor: tuple[MagicMock, MagicMock],
    mock_exporter: tuple[MagicMock, MagicMock],
) -> None:
    """Test the ExecutionHandler.post method with generic error."""
    _, executor_instance = mock_executor
    _, exporter_instance = mock_exporter

    # Set up the execution error with required parameters
    generic_error = RuntimeError("frombulator could not be whizzerated")

    executor_instance.preprocess.side_effect = generic_error

    executor_instance.nb = MagicMock()
    executor_instance.resources = MagicMock()

    notebook_str = (
        '{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}'
    )

    response = await jp_fetch(
        "rubin",
        "execution",
        method="POST",
        body=notebook_str,
        headers={"X-Kernel-Name": "python3"},
    )

    assert response.code == 200
    response_data = json.loads(response.body)
    assert "notebook" in response_data
    assert "resources" in response_data
    assert response_data["error"] is not None
    tb = response_data["error"]["traceback"]
    assert tb.startswith("Traceback (most recent call last)")
    assert tb == response_data["error"]["err_msg"]
    assert tb.endswith("RuntimeError: frombulator could not be whizzerated")
    assert response_data["error"]["ename"] == "RuntimeError"
    assert response_data["error"]["evalue"] == (
        "frombulator could not be whizzerated"
    )

    mock_nbformat_reads.assert_called_once()
    executor_instance.preprocess.assert_called_once()
    exporter_instance.from_notebook_node.assert_called_once_with(
        executor_instance.nb, resources=executor_instance.resources
    )


async def test_execution_handler_post_no_kernel_name(
    jp_fetch: Callable,
    mock_nbformat_reads: MagicMock,
    mock_executor: tuple[MagicMock, MagicMock],
    mock_exporter: tuple[MagicMock, MagicMock],
) -> None:
    """Test the ExecutionHandler.post method without kernel name."""
    _, executor_instance = mock_executor

    executor_instance.preprocess.return_value = None

    notebook_str = (
        '{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}'
    )

    # POST without X-Kernel-Name header
    response = await jp_fetch(
        "rubin", "execution", method="POST", body=notebook_str
    )

    assert response.code == 200
    mock_class, _ = mock_executor
    mock_class.assert_called_once_with()


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
        headers={"X-Kernel-Name": "python3"},
    )

    assert response.code == 200
    pdirs = list(tdir.glob("python*/site-packages/"))
    assert len(pdirs) == 2

    # Now retry, specifying the header but not the right value

    response = await jp_fetch(
        "rubin",
        "execution",
        method="POST",
        body=notebook_str,
        headers={
            "X-Kernel-Name": "python3",
            "X-Clear-Local-Site-Packages": "floof",
        },
    )

    assert response.code == 200
    pdirs = list(tdir.glob("python*/site-packages/"))
    assert len(pdirs) == 2

    # Retry with the header set to "false"
    response = await jp_fetch(
        "rubin",
        "execution",
        method="POST",
        body=notebook_str,
        headers={
            "X-Kernel-Name": "python3",
            "X-Clear-Local-Site-Packages": "false",
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
        headers={
            "X-Kernel-Name": "python3",
            "X-Clear-Local-Site-Packages": "TrUe",
        },
    )

    assert response.code == 200
    pdirs = list(tdir.glob("python*/site-packages/"))
    assert len(pdirs) == 0


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

    # Suppressing warnings with 'with warnings.catch_warnings():' doesn't work,
    # even when succeeded by warnings.simplefilter("ignore"); nor does the
    # ignore on its own.  In short, I don't know how to keep the test suite
    # from spewing all the warnings it receives.  These warnings are accurate
    # but I would like to suppress their display, since they are expected.
    #
    # Anyway, until I figure that out, the test suite barfs a lot of text
    # to the terminal when it runs.

    with caplog.at_level(logging.WARNING):
        response = await jp_fetch(
            "rubin",
            "execution",
            method="POST",
            body=notebook_str,
            headers={
                "X-Kernel-Name": "python3",
                "X-Clear-Local-Site-Packages": "True",
            },
        )

    assert response.code == 200
    assert "Permission denied: 'bad'" in caplog.text

    # Clean up; not sure all OSes will be sufficiently violent about
    # tempdirs with weird permissions.
    (sitep / "bad").chmod(mode=0o755)
    (sitep / "bad" / "bad").chmod(mode=0o644)
    shutil.rmtree(sitep)
