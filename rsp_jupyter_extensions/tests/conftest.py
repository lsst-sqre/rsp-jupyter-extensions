"""Fixture for test suite."""
import os
from pathlib import Path
import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

@pytest.fixture
def rsp_fs(
    fs: FakeFilesystem,
    monkeypatch: pytest.MonkeyPatch,
) -> FakeFilesystem:
    """Simulate enough of an RSP filesystem to run tests."""
    datadir = Path(__file__).parent / "data"
    fs.add_real_directory(datadir / "home", target_path="/home",
                               read_only=False)
    fs.add_real_directory(datadir / "usr", target_path="/usr",
                               read_only=False)
    monkeypatch.setenv("HOME", "/home/irian")
    env_p=os.getenv("PATH", "/bin:/usr/bin")
    env_p=f"/usr/local/bin:${env_p}"
    monkeypatch.setenv("PATH", env_p)
    return fs
