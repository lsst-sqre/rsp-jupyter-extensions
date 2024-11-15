"""Test that environment works."""

import json
import os
from collections.abc import Callable

import pytest


async def test_environment(jp_fetch: Callable) -> None:
    # When
    os.environ["TEST_KEY"] = "test_value"
    response = await jp_fetch("rubin", "environment")

    # Then
    assert response.code == 200
    payload = json.loads(response.body)
    assert payload["TEST_KEY"] == "test_value"
    with pytest.raises(KeyError):
        assert payload["DOES_THIS_KEY_EXIST"] == "no"
