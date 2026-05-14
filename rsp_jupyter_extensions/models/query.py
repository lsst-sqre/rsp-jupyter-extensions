"""Models for the query extension."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field


class TAPQuery(BaseModel):
    """TAP query mapping jobref ID to query text."""

    jobref: Annotated[str, Field(title="TAP jobref ID")]
    text: Annotated[str, Field(title="TAP query text")]
