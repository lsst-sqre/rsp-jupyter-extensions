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
