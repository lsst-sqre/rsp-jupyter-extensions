"""Test execution handler functionality."""

from collections.abc import Callable
from unittest.mock import MagicMock


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

    # POST without kernel_name param
    response = await jp_fetch(
        "rubin", "execution", method="POST", body=notebook_str
    )

    assert response.code == 200
    mock_class, _ = mock_executor
    mock_class.assert_called_once_with()
