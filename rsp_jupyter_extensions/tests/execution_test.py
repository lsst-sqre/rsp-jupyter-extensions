"""Test execution handler functionality."""

import json
from collections.abc import Callable, Generator
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
