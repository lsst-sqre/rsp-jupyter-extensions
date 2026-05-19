"""ServiceInfo model."""

from dataclasses import dataclass, field

__all__ = ["ServiceInfo"]


@dataclass
class ServiceInfo:
    """Service discovery information."""

    environment_name: str | None = field(default=None)
    datasets: dict[str, str] = field(default_factory=dict)
    ui: dict[str, str] = field(default_factory=dict)
    service: dict[str, str] = field(default_factory=dict)
