"""
Python module to initialize Server Extension for retrieving Rubin Observatory
settings.
"""
from .handlers import setup_handlers


def _jupyter_server_extension_paths():
    """
    Function to declare Jupyter Server Extension Paths.
    """
    exts = ("displayversion", "environment", "hub_comm", "query")
    # This comprehension actually works, but black can't handle it!
    # return [ {"module": f"rsp_jupyter_extensions.{ext}"} for ext in exts ]
    elist = []
    for ext in exts:
        elist.append({"module": f"rsp_jupyter_extensions.{ext}"})
    return elist


def load_jupyter_server_extension(nbapp):
    """
    Function to load Jupyter Server Extension.
    """
    nbapp.log.info("Loading rubin environment server extension.")
    setup_handlers(nbapp.web_app)
