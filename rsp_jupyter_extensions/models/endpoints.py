"""Endpoint model."""

from dataclasses import dataclass, field

__all__ = ["Endpoints"]


@dataclass
class Endpoints:
    """Endpoints used by this extension."""

    environment_name: str | None = field(
        default=None
    )  # Not really an endpoint
    datasets: dict[str, str] = field(default_factory=dict)
    ui: dict[str, str] = field(default_factory=dict)
    service: dict[str, str] = field(default_factory=dict)
