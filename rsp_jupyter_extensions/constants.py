"""Constants used by rsp-jupyter-extensions."""

from pathlib import Path

__all__ = ["CONFIG_FILE"]

CONFIG_FILE = Path("/etc/nublado/config/lab-config.json")
"""Path of mounted configmap for Nublado config.  Overrideable for testing."""
