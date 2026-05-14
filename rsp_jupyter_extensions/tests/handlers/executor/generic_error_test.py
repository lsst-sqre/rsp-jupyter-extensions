"""Test execution handler functionality."""

import json
from collections.abc import Callable
from unittest.mock import MagicMock


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
        params={"kernel_name": "python3"},
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
