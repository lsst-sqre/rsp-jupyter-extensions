"""Test that environment works with both abnormal and config endpoints."""

import json
from collections.abc import Callable

import pytest


async def test_abnormal(
    jp_fetch: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    # When
    monkeypatch.setenv("TEST_KEY", "test_value")
    response = await jp_fetch("rubin", "abnormal")

    # Then
    assert response.code == 200
    payload = json.loads(response.body)
    assert payload == {}

    monkeypatch.setenv("ABNORMAL_STARTUP", "TRUE")
    monkeypatch.setenv("NB_HOME", "/home/hambone")
    response = await jp_fetch("rubin", "abnormal")
    assert response.code == 200
    payload = json.loads(response.body)
    assert payload["ABNORMAL_STARTUP"] == "TRUE"
    assert payload["NB_HOME"] == "/home/hambone"
