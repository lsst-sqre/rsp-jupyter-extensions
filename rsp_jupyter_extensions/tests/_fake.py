"""Helper class for testing Jupyter handlers."""

from typing import Any

import tornado


class _FakeConnect(tornado.httputil.HTTPConnection):
    """Fake out the close callback."""

    def set_close_callback(self, arg: Any) -> None:
        pass
