"""Wrap JupyterLab browser check in respx mock."""

import json
import os
from pathlib import Path
from typing import Any

import jupyter_server.extension.application
import jupyterlab.browser_check
import pytest
import respx
from httpx import Response


class MockedExtensionApp(jupyter_server.extension.application.ExtensionApp):
    """Mock class that wraps launch_instance() in respx."""

    @classmethod
    def launch_instance(cls, argv: Any = None, **kwargs: Any) -> None:
        disco = json.loads(
            (
                Path(__file__).parent.parent
                / "data"
                / "etc"
                / "nublado"
                / "discovery_v1.json"
            ).read_text()
        )
        url = os.environ.get("REPERTOIRE_BASE_URL")
        if url is None:
            raise RuntimeError("REPERTOIRE_BASE_URL must be set")
        mocked = respx.get(url + "/discovery")
        mocked.return_value = Response(200, json=disco)
        super().launch_instance()


@respx.mock
def mock_check_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch Lab app to launch under respx."""
    _saved_extapp = jupyter_server.extension.application.ExtensionApp
    _saved_li = _saved_extapp.launch_instance

    monkeypatch.setattr(
        jupyter_server.extension.application,
        "ExtensionApp",
        MockedExtensionApp,
    )
    jupyterlab.browser_check.BrowserApp.launch_instance()
