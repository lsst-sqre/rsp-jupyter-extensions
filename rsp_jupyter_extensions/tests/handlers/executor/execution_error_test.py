"""Test execution handler functionality."""

import json
from collections.abc import Callable
from unittest.mock import MagicMock

from nbconvert.preprocessors import CellExecutionError


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
        params={"kernel_name": "python3"},
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
