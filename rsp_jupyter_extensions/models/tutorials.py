"""Models for the tutorial extensions."""

from __future__ import annotations

from enum import StrEnum, auto
from pathlib import Path
from typing import Annotated, Any, Self
from urllib.parse import urlparse, urlunparse

from pydantic import BaseModel, Field, model_validator


class Actions(StrEnum):
    """Allowable transformations for file movement."""

    COPY = auto()
    FETCH = auto()


class Dispositions(StrEnum):
    """Allowable choices for file conflict."""

    PROMPT = auto()
    OVERWRITE = auto()
    ABORT = auto()


class HierarchyError(Exception):
    """Class to indicate something went wrong with Hierarchy construction."""


class TagError(Exception):
    """Class to indicate something went wrong with the image tag."""


class UserEnvironmentError(Exception):
    """Class to indicate something went wrong with user environment."""


class HierarchyEntry(BaseModel):
    """A single entry representing a transformable object.

    We're really only using pydantic for its validation capabilities, since
    the object is going to be interchanged with the TypeScript UI layer and
    thus must be constructed from primitive types.
    """

    menu_name: Annotated[str, Field(title="Menu item name")]
    action: Annotated[Actions, Field(title="Transformation action")]
    disposition: Annotated[Dispositions, Field(title="Disposition action")]
    parent: Annotated[Path, Field(title="Menu parent")] = Path("/")
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

    @property
    def menu_path(self) -> Path:
        return self.parent / self.menu_name

    @model_validator(mode="after")
    def check_src_type(self) -> Self:
        if self.action == Actions.FETCH:
            try:
                _ = urlparse(str(self.src))
            except Exception as exc:
                raise HierarchyError(
                    "For action 'fetch', 'src' must be a URL"
                ) from exc
        if self.action == Actions.COPY:
            if not isinstance(self.src, Path):
                raise HierarchyError("For action 'copy', 'src' must be a Path")
        return self

    @staticmethod
    def _validate_fields(mut: dict[str, Any]) -> dict[str, str]:
        validated: dict[str, str] = {}
        for field in (
            "menu_name",
            "action",
            "disposition",
            "parent",
            "src",
            "dest",
        ):
            try:
                val = mut.pop(field)
            except KeyError:
                raise HierarchyError(f"'{field}' is not in {mut}") from None
            if not isinstance(val, str):
                raise HierarchyError(f"'{field}' is {val}, not a string")
            validated[field] = val
        # Make sure that menu_path is correct
        calc_path = str(Path(validated["parent"]) / validated["menu_name"])
        mval = mut.pop("menu_path", None)
        if mval is None:
            mval = calc_path
        if not isinstance(mval, str):
            raise HierarchyError(f"'{field}' is {mval}, not a string")
        if mval != calc_path:
            raise HierarchyError(
                f"'menu_path' is '{mval}', but should be '{calc_path}'"
            )
        validated["menu_path"] = calc_path
        # And now make sure we have no extraneous fields.
        kl = list(mut.keys())
        if kl:
            raise HierarchyError(f"Unknown fields {kl}")
        return validated

    @classmethod
    def from_primitive(cls, inp: dict[str, Any]) -> Self:
        """Convert from interchange format to Pydantic model type.

        Do model and type validation along the way.
        """
        mut: dict[str, Any] = {}
        mut.update(inp)
        validated = cls._validate_fields(mut)
        o_src: str | Path | None = None
        if validated["action"] == Actions.FETCH:
            o_act = Actions.FETCH
            o_src = urlunparse(urlparse(validated["src"]))
        elif validated["action"] == Actions.COPY:
            o_act = Actions.COPY
            o_src = Path(validated["src"])
        else:
            raise HierarchyError(
                f"'action'={validated['action']}: not in "
                f"{[str(x) for x in list(Actions)]}"
            )
        disps = [str(x) for x in list(Dispositions)]
        if validated["disposition"] not in disps:
            raise HierarchyError(
                f"'disposition'={validated['disposition']}: not in {disps}"
            )
        o_dis = Dispositions[(validated["disposition"].upper())]
        return cls(
            menu_name=validated["menu_name"],
            action=o_act,
            disposition=o_dis,
            parent=Path(validated["parent"]),
            src=o_src,
            dest=Path(validated["dest"]),
        )

    def to_primitive(self) -> dict[str, str | None]:
        """Return a representation suitable for JSON-decoding in TypeScript."""
        return {
            "menu_name": self.menu_name,
            "action": self.action.value,
            "disposition": self.disposition.value,
            "parent": str(self.parent),
            "menu_path": str(self.menu_path),
            "src": str(self.src),
            "dest": str(self.dest),
        }


class Hierarchy(BaseModel):
    """Pydantic validated version of tree structure."""

    entries: Annotated[
        dict[str, HierarchyEntry] | None,
        Field(title="Transformable file entries"),
    ] = None
    subhierarchies: Annotated[
        dict[str, Self] | None, Field(title="Transformable sub-hierarchies")
    ] = None

    @classmethod
    def from_primitive(cls, inp: dict[str, Any]) -> Self:
        """Create from JSON-serialized input."""
        mut: dict[str, Any] = {}
        mut.update(inp)
        try:
            entries = mut.pop("entries")
        except KeyError:
            raise HierarchyError(f"'entries' is not in {mut}") from None
        try:
            subhierarchies = mut.pop("subhierarchies")
        except KeyError:
            raise HierarchyError(f"'subhierarchies' is not in {mut}") from None
        kl = list(mut.keys())
        if kl:
            raise HierarchyError(f"Unknown fields {kl}")
        ret = cls()
        if entries:
            ret.entries = {}
            for entry in entries:
                val = entries[entry]
                if not isinstance(val, dict):
                    raise HierarchyError(f"'{entry}' -> '{val}' is not a dict")
                ret.entries[entry] = HierarchyEntry.from_primitive(val)
        if subhierarchies:
            ret.subhierarchies = {}
            for subh in subhierarchies:
                val = subhierarchies[subh]
                if not isinstance(val, dict):
                    raise HierarchyError(f"'{subh}' -> '{val}' is not a dict")
                ret.subhierarchies[subh] = cls.from_primitive(val)
        return ret

    def to_primitive(self) -> dict[str, Any]:
        h: dict[str, Any] = {}
        if self.entries:
            for entry in self.entries:
                if "entries" not in h or h["entries"] is None:
                    h["entries"] = {}
                h["entries"][entry] = self.entries[entry].to_primitive()
        if "entries" not in h:
            h["entries"] = None
        if self.subhierarchies:
            for subh in self.subhierarchies:
                if "subhierarchies" not in h or h["subhierarchies"] is None:
                    h["subhierarchies"] = {}
                h["subhierarchies"][subh] = self.subhierarchies[
                    subh
                ].to_primitive()
        if "subhierarchies" not in h:
            h["subhierarchies"] = None
        return h
