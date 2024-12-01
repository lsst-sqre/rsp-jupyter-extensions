"""Test that environment works."""

import json
from collections.abc import Callable

import pytest


async def test_environment(
    jp_fetch: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    # When
    monkeypatch.setenv("TEST_KEY", "test_value")
    response = await jp_fetch("rubin", "environment")

    # Then
    assert response.code == 200
    payload = json.loads(response.body)
    assert payload["TEST_KEY"] == "test_value"
    with pytest.raises(KeyError):
        assert payload["DOES_THIS_KEY_EXIST"] == "no"
