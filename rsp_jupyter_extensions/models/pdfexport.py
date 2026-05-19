"""Models for PDF Export."""

import json
from dataclasses import asdict, dataclass


@dataclass
class PDFExportResponse:
    """Simple wrapper for the response we will return to the caller.

    It has a "path" key and an "error" key.  If "path" is valid, "error" is
    ``None``, and vice versa.
    """

    path: str | None = None
    error: str | None = None

    def to_str(self) -> str:
        """Return JSON-serialized version of response."""
        self._validate()
        return json.dumps(asdict(self))

    def _validate(self) -> None:
        """Enforce that exactly one of the two fields is ``None``."""
        if self.path is None and self.error is None:
            self.error = "Both 'path' and 'error' cannot be 'None'"
        elif self.path is not None and self.error is not None:
            # The fact that there's an error invalidates the path.
            self.path = None
