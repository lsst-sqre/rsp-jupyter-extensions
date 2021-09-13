"""
Python module to initialize Server Extension for retrieving Rubin Observatory
settings.
"""
from .handlers import setup_handlers


def _jupyter_server_extension_paths():
    """
    Function to declare Jupyter Server Extension Paths.
    """
    # This comprehension actually works, but black can't handle it!
    # return [ {"module": f"rsp_jupyter_extensions.{ext}"} for ext in exts ]
    return [{"module": "rsp_jupyter_extensions"}]


def load_jupyter_server_extension(nbapp):
    """
    Function to load Jupyter Server Extension.
    """
    nbapp.log.info("Loading RSP server extensions.")
    setup_handlers(nbapp.web_app)
