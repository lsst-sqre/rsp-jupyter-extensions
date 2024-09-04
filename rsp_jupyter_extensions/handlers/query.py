"""
This is a Handler Module to provide an endpoint for templated queries.
"""
import json
import os
from pathlib import Path

from ._rspclient import RSPClient

import tornado

from jupyter_server.base.handlers import JupyterHandler
from urllib.parse import urljoin


class UnsupportedQueryTypeError(Exception):
    pass


class UnimplementedQueryResolutionError(Exception):
    pass


class QueryHandler(JupyterHandler):
    """
    RSP templated Query Handler.
    """

    def initialize(self) -> None:
        super().initialize()
        self._client = RSPClient(base_path="times-square/api/v1/")

    @property
    def rubinquery(self) -> dict[str, str]:
        return self.settings["rubinquery"]

    def _create_portal_query(self, q_value: str) -> str:
        # The value should be a URL
        url = q_value
        q_id = q_value.split("/")[-1]  # Last component is a unique query ID
        nb = self._get_portal_query_notebook(url)
        r_qdir = Path("notebooks") / "queries"
        qdir = Path(os.getenv("HOME", "")) / r_qdir
        qdir.mkdir(parents=True, exist_ok=True)
        fname = f"portal_{q_id}.ipynb"
        r_fpath = r_qdir / fname
        fpath = qdir / fname
        fpath.write_text(nb)
        retval = {
            "status": 200,
            "filename": str(fname),
            "path": str(r_fpath),
            "url": (
                os.environ.get("JUPYTERHUB_SERVICE_PREFIX", "")
                + "/tree/"
                + str(r_fpath)
            ),
            "body": nb,
        }
        return json.dumps(retval)

    def _get_portal_query_notebook(self, url: str) -> str:
        """Ask times-square for a rendered notebook."""

        # These are all constant for this kind of query
        org = "lsst-sqre"
        repo = "nublado-seeds"
        directory = "portal"
        notebook = "query"

        # Since we know the path we don't have to crawl the base github
        # response
        nb_url = f"github/{org}/{repo}/{directory}/{notebook}"

        # The only parameter we have is query_url, which is the Portal query
        # URL
        params = {"query_url": url}

        # Get the endpoint for the rendered URL
        obj = self._client.get(nb_url).json()
        rendered_url = obj["rendered_url"]

        # Retrieve that URL and return the textual response, which is the
        # string representing the rendered notebook "in unicode", which I
        # think means, "a string represented in the default encoding".
        return self._client.get(rendered_url, params=params).text


class PostQueryHandler(QueryHandler):
    @tornado.web.authenticated
    def post(self) -> None:
        """POST receives the query type and the query value as a JSON
        object containing "type" and "value" keys.  Each is a string.

        "type" is currently limited to "portal".

        For a Portal Query, "value" is the URL referring to that query.
        The interpretation of "value" is query-type dependent.

        It will then use the value to resolve the template, and will write
        a file with the template resolved under the user's
        "$HOME/notebooks/queries" directory.  That filename will also be
        derived from the type and value.
        """
        input_str = self.request.body.decode("utf-8")
        input_document = json.loads(input_str)
        q_type = input_document["type"]
        q_value = input_document["value"]
        if q_type != "portal":
            raise UnsupportedQueryTypeError(f"{q_type} is not a supported query type")
        q_fn = self._create_portal_query(q_value)
        self.write(q_fn)


class GetQueryHandler(JupyterHandler):
    """
    Get query with /rubin/portal_query/<q_id>.

    This is a convenience route to make writing a redirection route
    easier (since we just need to fill in q_id, and don't have to issue
    a POST).
    """

    @tornado.web.authenticated
    def get(self):
        components = [x for x in self.request.path.split("/") if x]
        if (len(components) < 2) or (components[-2] != "portal_query"):
            raise UnimplementedQueryResolutionError(
                f"{self.request.path} is not a supported query url"
            )
        q_id = components[-1]
        base_url = self.request.host
        q_url = str(urljoin(base_url, f"/api/tap/async/{q_id}"))
        q_fn = self._create_portal_query(q_url)
        self.write(q_fn)
