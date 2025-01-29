"""Exercise backend handlers."""

import json
import os
from collections.abc import Callable


async def test_environment(jp_fetch: Callable) -> None:
    """Test that the environment exists and returns a test key/value."""
    # When
    os.environ["TEST_KEY"] = "test_value"
    response = await jp_fetch("rubin", "environment")

    # Then
    assert response.code == 200
    payload = json.loads(response.body)
    assert payload["TEST_KEY"] == "test_value"
