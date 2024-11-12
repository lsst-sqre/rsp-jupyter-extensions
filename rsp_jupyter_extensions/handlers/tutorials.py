from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

import tornado

from jupyter_server.base.handlers import JupyterHandler
from lsst.rsp.startup.storage.command import Command

# https://stephantul.github.io/python/mypy/types/2024/02/05/hierarchy/
Hierarchy = dict[str, dict[str, str] | Hierarchy]


def _build_hierarchy(
    root: Path,
    action: str = "copy",
    xform_src: Callable[[str], str] = lambda x: x,
    xform_dest: Callable[[str], str] = lambda x: x,
    suffix: str | None = None,
) -> Hierarchy:
    h: Hierarchy = {}
    sortlist = list(root.iterdir())
    sortlist.sort(key=lambda x: x.name)
    for entry in sortlist:
        if entry.is_dir():
            subdir = _build_hierarchy(root=entry, suffix=suffix)
            if subdir:
                h[entry.name] = subdir
            continue
        nm = entry.name
        if suffix:
            if not nm.endswith(suffix):
                continue
            nm = nm[: -len(suffix)]
        h[nm] = {
            "action": action,
            "src": xform_src(str(entry)),
            "dest": xform_dest(str(entry)),
        }


# _find_repo and _get_tag might belong in lsst.rsp.


def _find_repo() -> str | None:
    # Eventually we may not even want to set AUTO_REPO_SPECS...
    auto_repos = os.getenv("AUTO_REPO_SPECS")
    if not auto_repos:
        # This instance doesn't want them
        return None
    repos = auto_repos.split(",")
    for repo in repos:
        if repo.find("tutorial-notebooks") > -1:
            break
    atsign = repo.find("@")
    if atsign == -1:
        repo += "@main"
    return repo


def _clone_repo(repo_url: str, branch: str) -> None:
    cmd = Command()
    proc = cmd.run(
        "git",
        "clone",
        "--depth",
        "1",
        repo_url,
        "-b",
        branch,
        "/tmp/tutorial-notebooks",  # Literal; do not use TMPDIR
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git clone {repo_url}@{branch} failed")


def _get_tag() -> str:
    image = os.getenv("JUPYTER_IMAGE_SPEC")
    if not image:
        raise RuntimeError("Environment variable 'JUPYTER_IMAGE_SPEC' is not set")
    colon = image.find(":")
    atsign = image.find("@")
    if colon < 0 or atsign <= colon:
        raise RuntimeError("Could not extract tag from image spec")
    tag = image[colon + 1 : atsign]
    if not tag:
        raise RuntimeError("Could not determine image tag")
    return tag


class TutorialsMenuHandler(JupyterHandler):
    """This produces a JSON representation of the layout of the on-disk
    tutorials that were baked into the container at build time, and will
    do a clone of the current state of the tutorial repository to get that
    information at execution time.  This information is intended for
    consumption by the Tutorials menu.

    In general we expect this endpoint to be invoked only once, at container
    start time.  Once we have values for the trees, we cache them, and will
    require a container restart to update those values.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.tutorials: Hierarchy | None = None
        self._populate_tutorials()

    def _populate_tutorials(self) -> None:
        if self.tutorials:
            return
        self._get_resident_tutorials()
        self._get_github_tutorials()

    def _get_resident_tutorials() -> Hierarchy:
        homedir = os.getenv("HOME")
        if not homedir:
            raise RuntimeError("Home directory is not set")
        tag = _get_tag()
        if not tag:
            raise RuntimeError("Image tag cannot be determined")
        tutorial_dir = Path(homedir) / "notebooks" / "tutorials" / tag
        prefix = "/opt/lsst/software/notebooks-at-build-time/"  # by convention

        def _xform(src: str) -> str:
            if not src.startswith(prefix):
                raise RuntimeError("File '{src}' does not begin with '{prefix}'")
            rest = src[len(prefix) :]
            return str(tutorial_dir / rest)

        return _build_hierarchy(
            prefix, suffix=".ipynb", action="copy", xform_dest=_xform
        )

    def _get_github_tutorials() -> Hierarchy:
        homedir = os.getenv("HOME")
        if not homedir:
            raise RuntimeError("Home directory is not set")
        tutorial_dir = Path(homedir) / "notebooks" / "tutorials" / "latest"
        repo = _find_repo()
        if not repo:
            return {}
        repo_url, branch = repo.split("@")
        if not branch:
            # This is to placate mypy: _find_repo() will append @main if needed
            branch = "main"
        _clone_repo(repo_url, branch)
        prefix = "/tmp/tutorial-notebooks/"

        def _xform_src(src: str) -> str:
            # From our cloned copy, reverse-engineer the direct download
            # file URLs for each notebook.
            if not src.startswith(prefix):
                raise RuntimeError("File '{src}' does not begin with '{prefix}'")
            rest = src[len(prefix) :]
            return f"{repo_url}/raw/refs/heads/{branch}/{rest}"

        def _xform(src: str) -> str:
            if not src.startswith(prefix):
                raise RuntimeError("File '{src}' does not begin with '{prefix}'")
            rest = src[len(prefix) :]
            return str(tutorial_dir / rest)

        return _build_hierarchy(
            prefix,
            suffix=".ipynb",
            action="fetch",
            xform_src=_xform_src,
            xform_dest=_xform,
        )

    @tornado.web.authenticated
    def get(self) -> None:
        self.log.info("Sending Tutorials menu information")
        if self.tutorials:
            self.write(json.dumps(self.tutorials or {}))
