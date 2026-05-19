"""Test execution handler functionality."""

import json
from collections.abc import Callable
from unittest.mock import MagicMock


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
        params={"kernel_name": "python3"},
    )

    assert response.code == 200
    response_data = json.loads(response.body)
    assert "notebook" in response_data
    assert "resources" in response_data
    assert response_data["error"] is None

    # Verify method calls with resources
    mock_nbformat_reads.assert_called_once()
    executor_instance.preprocess.assert_called_once()
