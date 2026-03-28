"""Test that environment works."""

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
    response = await jp_fetch("rubin", "abnormal")
    assert response.code == 200
    payload = json.loads(response.body)
    assert payload["ABNORMAL_STARTUP"] == "TRUE"
