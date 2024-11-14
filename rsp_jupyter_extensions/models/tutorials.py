"""Models for the tutorial extensions."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

from urllib.parse import urlparse, urlunparse

ACTIONS = Literal["copy", "fetch"]
DISPOSITIONS = Literal["prompt", "overwrite", "abort"]


class HierarchyEntry(BaseModel):
    """A single entry representing a transformable object.

    We're really only using pydantic for its validation capabilities, since
    the object is going to be interchanged with the TypeScript UI layer and
    thus must be constructed from primitive types.
    """

    action: Annotated[ACTIONS, Field(title="Transformation action")]
    disposition: Annotated[DISPOSITIONS, Field(title="Disposition action")]
    parent: Annotated[Path | None, Field(title="Menu parent")] = None
    src: Annotated[
        Path | str,
        Field(
            "Document source",
            description="Source (URL or path) for item",
        ),
    ]
    dest: Annotated[
        Path,
        Field(
            "Document destination in user Lab",
            description="Destination for item",
        ),
    ]

    @model_validator(mode="after")
    def check_src_type(self) -> Self:
        if self.action == "fetch":
            try:
                _ = urlparse(self.src)
            except Exception as exc:
                raise ValueError("For action 'fetch', 'src' must be a URL") from exc
        if self.action == "copy":
            if not isinstance(self.src, Path):
                raise ValueError("For action 'copy', 'src' must be a Path")
        return self

    @classmethod
    def from_primitive(cls, inp: PrimitiveHierarchyEntry) -> Self:
        """Convert from interchange format to Pydantic model type."""
        if inp.action == "fetch":
            o_src = urlunparse(urlparse(inp.src))
        else:
            o_src = Path(inp.src)
        return cls(
            action=inp["action"],
            disposition=inp["disposition"],
            parent=inp["parent"],
            src=o_src,
            dest=Path(inp["dest"]),
        )

    def to_primitive(self) -> PrimitiveHierarchyEntry:
        """Return a representation suitable for JSON-decoding in TypeScript."""
        return {
            "action": self.action,
            "disposition": self.disposition,
            "parent": str(self.parent) if self.parent else None,
            "src": str(self.src),
            "dest": str(self.dest),
        }


# https://stephantul.github.io/python/mypy/types/2024/02/05/hierarchy/
# This one is the interchange type version.

# Self requires Python 3.11, which the JupyterLab extension machinery may
# object to; if that fails replace 'Self' with '"Hierarchy"'.

# We know we're running Python 3.11 or later, since the DM stack for one-
# Python versions is 3.11 as of rsp_env 9.0.0, and for two-Python versions
# we're starting at 3.12.  An arbitrary JupyterLab installation may not be.

Hierarchy = dict[str, [str | Self]]

PrimitiveHierarchyEntry = dict[str, str]
