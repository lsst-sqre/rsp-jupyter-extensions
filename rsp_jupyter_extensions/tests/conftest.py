"""Fixture for test suite."""
import os
from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem
import respx

from rubin.repertoire import Discovery, register_mock_discovery

@pytest.fixture(autouse=True)
def mock_discovery(
    respx_mock: respx.Router, monkeypatch: pytest.MonkeyPatch
) -> Discovery:
    monkeypatch.setenv("REPERTOIRE_BASE_URL", "https://example.lsst.cloud/repertoire")
    path = (Path(__file__).parent / "data" / "etc" / "nublado"
            / "discovery_v1.json")
    return register_mock_discovery(respx_mock, path)

def _add_real_directory(
    fs:FakeFilesystem,
    pathname: str
) -> None:
    datadir = Path(__file__).parent / "data"
    fs.add_real_directory(
        datadir / pathname,
        target_path = f"/{pathname}",
        read_only = True
    )

@pytest.fixture
def rsp_fs(
    fs: FakeFilesystem,
    monkeypatch: pytest.MonkeyPatch,
) -> FakeFilesystem:
    """Simulate enough of an RSP filesystem to run tests."""
    for dd in ("etc", "home", "usr"):
        _add_real_directory(fs, dd)
    monkeypatch.setenv("HOME", "/home/irian")
    env_p=os.getenv("PATH", "/bin:/usr/bin")
    env_p=f"/usr/local/bin:{env_p}"
    monkeypatch.setenv("PATH", env_p)
    return fs

@pytest.fixture
def tutorial_env(tmp_path:Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Environment for tutorial tests; pyfakefs doesn't work here
    because setting up the handler internally uses subprocess and the
    in-memory fake filesystem doesn't persist across the spawned
    process.
    """
    monkeypatch.setenv("REPERTOIRE_BASE_URL", "https://example.com/repertoire")
    # Set up test files
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "subsubdir").mkdir()
    for p in (
        tmp_path,
        tmp_path / "subdir",
        tmp_path / "subdir" / "subsubdir",
    ):
        (p / "hello.txt").write_text("Hello, world!\n")
        (p / "hello.py").write_text("print('Hello, world!')\n")
    # Create .git directory so we don't pull the repo.
    (tmp_path / ".git").mkdir()

    return tmp_path
