"""Test that environment works with both abnormal and config endpoints."""

import json
from collections.abc import Callable

from pyfakefs.fake_filesystem import FakeFilesystem


async def test_serviceinfo(
    jp_fetch: Callable,
    rsp_fs: FakeFilesystem,
) -> None:
    """Test `serviceinfo` endpoint."""
    response = await jp_fetch("rubin", "serviceinfo")
    assert response.code == 200
    payload = json.loads(response.body)
    assert payload == {
        "environment_name": "example.lsst.cloud",
        "datasets": {
            "dp02": "https://example.lsst.cloud/api/tap",
            "dp03": "https://example.lsst.cloud/api/ssotap",
            "dp1": "https://example.lsst.cloud/api/tap",
            "prompt": "https://example.lsst.cloud/api/ppdbtap",
        },
        "service": {
            "times-square": "https://example.lsst.cloud/times-square/api",
        },
        "ui": {
            "logout": "https://example.lsst.cloud/logout",
            "squareone": "https://example.lsst.cloud/",
        },
    }
