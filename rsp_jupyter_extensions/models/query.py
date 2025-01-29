"""Models for the query extension."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field


class UnsupportedQueryTypeError(Exception):
    """Request for a query of a type we don't know about."""


class UnimplementedQueryResolutionError(Exception):
    """Request for a query where the parameters are not resolvable."""


class TAPQuery(BaseModel):
    """TAP query mapping jobref ID to query text."""

    jobref: Annotated[str, Field(title="TAP jobref ID")]
    text: Annotated[str, Field(title="TAP query text")]
