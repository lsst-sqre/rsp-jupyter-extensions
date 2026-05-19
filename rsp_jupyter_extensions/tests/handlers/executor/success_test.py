"""Test execution handler functionality."""

import json
from collections.abc import Callable
from unittest.mock import MagicMock


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
        params={"kernel_name": "python3"},
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
