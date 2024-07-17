"""
This is a Handler Module to provide an endpoint for templated queries.
"""
import json
import os
from pathlib import Path

import tornado

from jupyter_server.base.handlers import JupyterHandler

from jinja2 import Template

PORTAL_QUERY_TEMPLATE = """
{
 "cells": [
  { "cell_type": "markdown",
    "metadata": {},
    "source": [
    "### This notebook was rendered using `query_url` = {{QUERY_URL}}"
    ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "from lsst.rsp import retrieve_query\\n",
    "query_url = \\\"{{QUERY_URL}}\\\"\\n",
    "query_data = retrieve_query(query_url)\\n"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "LSST",
   "language": "python",
   "name": "lsst"
  },
  "language_info": {
   "name": ""
  }
 },
 "nbformat": 4,
 "nbformat_minor": 5
}
"""


class UnsupportedQueryTypeError(Exception):
    pass


class UnimplementedQueryResolutionError(Exception):
    pass


class Query_handler(JupyterHandler):
    """
    RSP templated Query Handler.
    """

    @property
    def rubinquery(self) -> dict[str, str]:
        return self.settings["rubinquery"]

    @tornado.web.authenticated
    def post(self) -> None:
        """POST receives the query type and the query value as a JSON
        object containing "type" and "value" keys.  Each is a string.

        "type" is currently limited to "portal".

        For a Portal Query, "value" is the URL referring to that query.
        The interpretation of "value" is query-type dependent.

        We should have some sort of template service.  For right now, we're
        just going to go with a very dumb string substitution.

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

    def _create_portal_query(self, q_value: str) -> str:
        # The value should be a URL
        url = q_value
        q_id = q_value.split("/")[-1]  # Last component is a unique query ID
        nb_tpl = Template(PORTAL_QUERY_TEMPLATE)
        nb = nb_tpl.render(QUERY_URL=url)
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
