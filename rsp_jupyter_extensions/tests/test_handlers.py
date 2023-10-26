import json
import os


async def test_environment(jp_fetch):
    # When
    os.environ["TEST_KEY"] = "test_value"
    response = await jp_fetch("rubin", "environment")

    # Then
    assert response.code == 200
    payload = json.loads(response.body)
    assert payload["TEST_KEY"] == "test_value"
