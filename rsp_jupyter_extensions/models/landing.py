"""Models for the landing extension."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field


class LandingResponse(BaseModel):
    """Response from landing page extension for UI."""

    dest: Annotated[str, Field(title="Landing page path")]
    cached: Annotated[bool, Field(title="Was response cached")]
