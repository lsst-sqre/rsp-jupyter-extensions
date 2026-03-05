"""Server-side query handler for tutorial menu."""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx
import tornado
from jupyter_server.base.handlers import APIHandler

from ..models.tutorials import (
    Actions,
    Dispositions,
    Hierarchy,
    HierarchyEntry,
    HierarchyError,
    TagError,
    UserEnvironmentError,
)
from ._utils import _browser_path_to_file, _file_to_browser_path, _get_config


def _find_repo() -> str | None:
    repo = os.getenv(
        "TUTORIAL_NOTEBOOKS_URL",
        "https://github.com/lsst/tutorial-notebooks@main",
    )
    if "@" not in repo:
        repo += "@main"
    return repo


def _get_tag() -> str:
    try:
        cfg_obj = _get_config()
        image = cfg_obj["image"]["spec"]
    except Exception:
        raise UserEnvironmentError("Could not determine image spec") from None
    colon = image.find(":")
    atsign = image.find("@")
    if colon < 0 or atsign <= colon:
        raise TagError("Could not extract tag from image spec")
    tag = image[colon + 1 : atsign]
    if not tag:
        raise TagError("Could not determine image tag")
    return tag


# Generic clone method


def _clone_repo(repo_url: str, branch: str, dirname: str) -> None:
    proc = subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            repo_url,
            "-b",
            branch,
            dirname,
        ],
        capture_output=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git clone {repo_url}@{branch} failed")


def _get_homedir() -> Path:
    return Path(os.environ["HOME"])  # $HOME must be set for lab to launch.


# RSP-specific tutorial locations


def _check_tutorials_hierarchy_stash() -> Hierarchy | None:
    # This is a little subtle.  We get a new instance of the handler with
    # every access of its endpoints, and however Jupyter Server manages that
    # it really needs to be a new one--making the handler a singleton does
    # not work (it doesn't respond to its endpoints).
    #
    # So what we do is to check the presence of a serialized hierarchy
    # in a known location inside the user's homedir.  If it exists, it
    # is sufficiently new (let's start with 8 hours or less), and it
    # has a subhierarchy matching the current tag, then we deserialize it
    # and return that.
    #
    # If it does not exist or is potentially stale...we return None from
    # here, which then allows the clone to proceed, and we rebuild the stash
    # from those results.
    max_age = datetime.timedelta(hours=8)
    homedir = _get_homedir()
    stash = homedir / ".cache" / "tutorials.json"
    if not stash.is_file():
        return None
    mod = datetime.datetime.fromtimestamp(
        stash.stat().st_mtime, tz=datetime.UTC
    )
    now = datetime.datetime.now(tz=datetime.UTC)
    age = now - mod
    if age > max_age:
        return None
    try:
        tut_obj = json.loads(stash.read_text())
    except json.decoder.JSONDecodeError:
        return None
    try:
        cfg_obj = _get_config()
        resident_tag = cfg_obj["image"]["description"]
    except Exception:
        resident_tag = "resident"
    if (
        "subhierarchies" not in tut_obj
        or resident_tag not in tut_obj["subhierarchies"]
    ):
        return None
    return Hierarchy.from_primitive(tut_obj)


def _reabsolutize_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    # We need to re-absolutize it so it doesn't get written to wherever
    # the Lab extension is running from.
    return _browser_path_to_file(str(path))


async def _copy_content(entry: HierarchyEntry) -> None:
    # Note that we assume we've already decided we want to do this (that is,
    # the check for Disposition and a file conflict has already happened).
    #
    # Also, these objects are typically notebooks and should not have
    # outputs in them.  If they don't easily fit into memory, something
    # else is wrong.
    dest = _reabsolutize_path(entry.dest)
    dest.parent.mkdir(exist_ok=True, parents=True)
    if entry.action == Actions.FETCH:
        if not isinstance(entry.src, str):
            # The typing should already be correct because of our model
            # validation, but ruff needs some convincing.
            entry.src = str(entry.src)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(entry.src, timeout=30)
        with dest.open("wb") as fd:
            for chunk in resp.iter_bytes(chunk_size=int(1e6)):
                fd.write(chunk)
    else:
        if not isinstance(entry.src, Path):
            # Same story on the typing.
            entry.src = Path(entry.src)
        shutil.copy(entry.src, dest)


def _check_containment(dest: Path) -> None:
    """Check whether the path is reachable in the file browser."""
    abs_dest = _reabsolutize_path(dest)
    route = _file_to_browser_path(abs_dest)
    if route is None:
        raise HierarchyError(
            f"'{abs_dest!s}' is not reachable in the file browser"
        )


async def _copy_and_guide(input_document: dict[str, Any]) -> _UIGuidance:
    entry = HierarchyEntry.from_primitive(input_document)
    dest = Path(entry.dest)
    dest = _reabsolutize_path(dest)
    _check_containment(dest)
    if dest.exists():
        disposition = entry.disposition
        if disposition == Dispositions.PROMPT:
            # Send a 409 back to the UI and let it decide what to do.
            return _UIGuidance(status_code=409)
        elif disposition == Dispositions.ABORT:
            # Shouldn't get here--just don't send a request from UI
            # layer instead.
            return _UIGuidance(status_code=204)
        else:
            # Otherwise, just fall through and overwrite the file.
            pass
    await _copy_content(entry)
    # We don't want to issue the redirect, because we don't want to
    # mess with opening a new window in the JupyterLab API.  Instead,
    # we should just return a 200 with the destination field filled out
    # with a path relative to the notebook dir, which we can assume to
    # be ${HOME}, and let the UI extension handle opening the file it
    # finds there.
    guide = _file_to_browser_path(entry.dest)
    return _UIGuidance(status_code=200, dest=guide)


@dataclass
class _UIGuidance:
    status_code: int
    dest: str | None = None


class TutorialsMenuHandler(APIHandler):
    """Produce a JSON representation of the layout of the on-disk
    tutorials that were baked into the container at build time: will
    do a clone of the current state of the tutorial repository to get that
    information at execution time.  This information is intended for
    consumption by the Tutorials menu.

    Once we have values for the trees, we cache them, and will
    require a container restart to update those values.
    """

    def initialize(self) -> None:
        super().initialize()
        self.log.info("Initializing TutorialsMenuHandler.")
        self.tutorials: Hierarchy | None = None
        self._populate_tutorials()

    def _populate_tutorials(self) -> None:
        if self.tutorials:
            return
        stash = _check_tutorials_hierarchy_stash()
        if stash:
            self.tutorials = stash
            return
        # Need to rebuild the structure.
        # Do we have a cache directory?  Then use it.
        if dirname := os.getenv("TUTORIAL_NOTEBOOKS_CACHE_DIR", ""):
            self.tutorials = self._get_github_tutorials(
                dirname, from_cache=True
            )
        else:
            # Or get a new clone and use that.
            with TemporaryDirectory() as dirname:
                self.tutorials = self._get_github_tutorials(dirname)
        # And write a stash
        homedir = _get_homedir()
        stashfile = homedir / ".cache" / "tutorials.json"
        stashfile.parent.mkdir(exist_ok=True)
        stashfile.write_text(json.dumps(self.tutorials.to_primitive()))

    @tornado.web.authenticated
    async def get(self) -> None:
        """Retrieve information about our tutorials."""
        self.log.info("Sending Tutorials menu information")
        if self.tutorials is None:  # It shouldn't be.
            self.write(json.dumps({}))
            return
        self.write(json.dumps(self.tutorials.to_primitive()))

    @tornado.web.authenticated
    async def post(self) -> None:
        """Do the copy and return guide to the UI."""
        self.log.info("Received POST request for tutorial copy")
        input_str = self.request.body.decode("utf-8")
        input_document = json.loads(input_str)
        guide = await _copy_and_guide(input_document)
        self.log.debug(f"Copy/guide got: {guide}")
        if guide.dest is None:
            dest = input_document["dest"]
            self.log.warning(f"File {dest} already exists.")
            if guide.status_code == 409:
                self.log.warning("Returning to UI")
                self.send_error(409)
            elif guide.status_code == 204:
                self.log.warning("Abandoning copy request")
            else:
                self.log.error(f"Unknown redir state {guide.status_code}")
                if guide.status_code >= 400:
                    self.send_error(guide.status_code)
                else:
                    self.set_status(guide.status_code)
            return
        self.log.debug(f"Replying with dest = '{guide.dest}'")
        self.write(json.dumps({"dest": guide.dest}))

    def _get_github_tutorials(
        self, dirname: str, *, from_cache: bool = False
    ) -> Hierarchy:
        homedir = _get_homedir()
        tutorial_dir = homedir / "notebooks" / "tutorials"
        use_cache = from_cache
        if use_cache:
            self.log.debug(f"get_gh: Checking cached repo {dirname}")
            # Does it appear to be a git repo?
            repo_git = Path(dirname) / ".git"
            if not repo_git.is_dir():
                self.log.debug("get_gh: Not a repo: force new clone")
                use_cache = False  # force new clone
        repo = _find_repo()
        if not repo:
            self.log.debug("get_gh: No repository found")
            return Hierarchy()
        repo_url, branch = repo.split("@")
        branch = branch or "main"
        if not use_cache:
            self.log.debug("get_gh: New clone")
            self.log.debug(f"Cloning {repo_url} branch {branch} to {dirname}")
            _clone_repo(repo_url, branch, dirname)
        dir_obj = Path(dirname)

        def _xform_src(src: Path | str) -> str:
            # From our cloned copy, reverse-engineer the direct download
            # file URLs for each notebook.
            if isinstance(src, str):
                src = Path(src)
            rest = src.relative_to(dir_obj)
            return urlunparse(
                urlparse(f"{repo_url}/raw/refs/heads/{branch}/{rest!s}")
            )

        def _xform(src: Path) -> Path:
            start_dir = Path(_get_homedir())
            try:
                cfg = _get_config()
                if cfg["file_browser_root"] == "root":
                    start_dir = Path("/")
            except Exception:
                self.log.warning(
                    "Failed to read config; assuming file browser root is"
                    " homedir."
                )
            rest = src.relative_to(dir_obj)
            return (tutorial_dir / rest).relative_to(Path(start_dir))

        return self._build_hierarchy(
            dir_obj,
            parent=Path("/"),
            suffix=".ipynb",
            action=Actions.FETCH,
            xform_src=_xform_src,
            xform_dest=_xform,
        )

    def _build_hierarchy(
        self,
        root: Path,
        parent: Path = Path("/"),
        action: Actions = Actions.COPY,
        disposition: Dispositions = Dispositions.PROMPT,
        xform_src: Callable[[str | Path], str | Path] = lambda x: x,
        xform_dest: Callable[[Path], Path] = lambda x: x,
        suffix: str | None = None,
    ) -> Hierarchy:
        h = Hierarchy()
        sortlist = list(root.iterdir())
        sortlist.sort(key=lambda x: x.name)
        for entry in sortlist:
            self.log.debug(f"build_hierarchy: considering {entry.name}")
            # We may want to make this more sophisticated sometime.
            if entry.is_symlink():
                # Just skip any symbolic links.
                self.log.debug(f"Skipping symlink {entry.name}")
                continue
            if entry.is_dir():
                if entry.name == ".git":
                    # Skip the Git objects dir: the tutorials hierarchy is
                    # not intended for pushing back up (consider that
                    # the repository tags probably do not match the eups
                    # container tag)
                    self.log.warning(
                        "build_hierarchy: Skipping .git directory"
                    )
                    continue
                next_parent = parent / entry.name
                # Recurse down the tree.
                self.log.debug(f"build_hierarchy: recurse on {next_parent!s}")
                subdir = self._build_hierarchy(
                    root=entry,
                    parent=next_parent,
                    action=action,
                    xform_src=xform_src,
                    xform_dest=xform_dest,
                    suffix=suffix,
                )
                if (
                    subdir.subhierarchies is not None
                    or subdir.entries is not None
                ):
                    if h.subhierarchies is None:
                        h.subhierarchies = {}
                    self.log.debug(
                        f"build_hierarchy: adding child {entry.name}"
                    )
                    h.subhierarchies[entry.name] = subdir
                continue  # Done with directory.
            # It's a file.
            nm = entry.name
            if suffix:
                if not nm.endswith(suffix):
                    continue
                nm = nm[: -len(suffix)]
            self.log.debug(f"build_hierarchy: Adding file entry {nm}")
            h_entry = HierarchyEntry(
                menu_name=nm,
                action=action,
                disposition=Dispositions.PROMPT,
                parent=parent,
                src=xform_src(entry),
                dest=xform_dest(entry),
            )
            if h.entries is None:
                h.entries = {}
            h.entries[nm] = h_entry
        return h
