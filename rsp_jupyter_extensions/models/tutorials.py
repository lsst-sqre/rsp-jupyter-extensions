"""Models for the tutorial extensions."""
from __future__ import annotations

from enum import StrEnum, auto
from pathlib import Path
from typing import Annotated, Self, Union

from pydantic import BaseModel, Field, model_validator

from urllib.parse import urlparse, urlunparse


class Actions(StrEnum):
    COPY = auto()
    FETCH = auto()


class Dispositions(StrEnum):
    PROMPT = auto()
    OVERWRITE = auto()
    ABORT = auto()


class HierarchyEntry(BaseModel):
    """A single entry representing a transformable object.

    We're really only using pydantic for its validation capabilities, since
    the object is going to be interchanged with the TypeScript UI layer and
    thus must be constructed from primitive types.
    """

    action: Annotated[Actions, Field(title="Transformation action")]
    disposition: Annotated[Dispositions, Field(title="Disposition action")]
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
        if self.action == Actions.FETCH:
            try:
                _ = urlparse(str(self.src))
            except Exception as exc:
                raise ValueError("For action 'fetch', 'src' must be a URL") from exc
        if self.action == Actions.COPY:
            if not isinstance(self.src, Path):
                raise ValueError("For action 'copy', 'src' must be a Path")
        return self

    @classmethod
    def from_primitive(cls, inp: PrimitiveHierarchyEntry) -> Self:
        """Convert from interchange format to Pydantic model type.

        Do model and type validation along the way."""

        validated: dict[str, str] = {}
        for field in ("action", "disposition", "src", "dest"):
            val = inp.pop(field)
            if not isinstance(val, str):
                raise ValueError(f"'{field}' is {val}, not a string")
        parent = inp.pop("parent")
        if parent is not None and not isinstance(parent, str):
            raise ValueError(f"'parent' is {parent}, neither a string nor None")
        kl = list(inp.keys())
        if kl:
            raise ValueError(f"Unknown keys {kl}")
        o_src: str | Path | None = None
        if validated["action"] == Actions.FETCH:
            o_act = Actions.FETCH
            o_src = urlunparse(urlparse(validated["src"]))
        elif validated["action"] == Actions.COPY:
            o_act = Actions.COPY
            o_src = Path(validated["src"])
        else:
            raise ValueError(
                f"'action'={validated['action']}: not in "
                f"{[str(x) for x in list(Actions)]}"
            )
        disps = [str(x) for x in list(Dispositions)]
        if inp["disposition"] not in disps:
            raise ValueError(
                f"'disposition'={validated['disposition']}: not in {disps}"
            )
        o_dis = Dispositions[(inp["disposition"].upper())]
        return cls(
            action=o_act,
            disposition=o_dis,
            parent=Path(parent) if parent else None,
            src=o_src,
            dest=Path(validated["dest"]),
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

type Hierarchy = dict[str, Union[str | "Hierarchy" | None]]
type HierarchyModel = dict[str, Union[str | "HierarchyModel" | None]]
type PrimitiveHierarchyEntry = dict[str, str | None]
