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
    monkeypatch.setenv("TUTORIAL_NOTEBOOKS_CACHE_DIR", str(tmp_path))

    return tmp_path
