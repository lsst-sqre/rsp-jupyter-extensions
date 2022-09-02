"""
This is a Handler Module to provide an endpoint for templated queries
"""
import json
import os
from os.path import dirname, join
from typing import Dict

from jinja2 import Template
from notebook.base.handlers import APIHandler

SUPPORTED_QUERY_TYPES = ["portal"]


class UnsupportedQueryTypeError(Exception):
    pass


class UnimplementedQueryResolutionError(Exception):
    pass


class Query_handler(APIHandler):
    """
    RSP templated Query Handler.
    """

    @property
    def rubinquery(self) -> Dict[str, str]:
        return self.settings["rubinquery"]

    def post(self) -> None:
        """POST receives the query type and the query value as a JSON
        object containing "type" and "value" keys.  Each is a string.

        "type" is currently limited to "portal" (generally: it
        must be in SUPPORTED_QUERY_TYPES).

        For a Portal Query, "value" is the URL referring to that query.
        The interpretation of "value" is query-type dependent.

        Generally, the post will load a notebook template from the
        "templates" directory (relative to this handler) whose name is
        <type>_query.ipynb.template.

        It will then use the value to resolve the template, and will write
        a file with the template resolved under the user's
        "$HOME/notebooks/queries" directory.  That filename will also be
        derived from the type and value.
        """
        input_str = self.request.body.decode("utf-8")
        input_document = json.loads(input_str)
        q_type = input_document["type"]
        q_value = input_document["value"]
        if q_type not in SUPPORTED_QUERY_TYPES:
            raise UnsupportedQueryTypeError(
                f"{q_type} is not a supported query type"
            )
        q_fn = self._create_query(q_type, q_value)
        self.finish(q_fn)

    def _create_query(self, q_type: str, q_value: str) -> str:
        dir: str = join(dirname(__file__), "templates")
        fn = join(dir, q_type + "_query.ipynb.template")
        with open(fn) as f:
            txt = f.read()
            tmpl = Template(txt)
        if q_type == "portal":
            q_result = self._create_portal_query(q_value, tmpl)
        else:
            raise UnimplementedQueryResolutionError(
                f"{q_type} does not have a method of template resolution"
            )
        return q_result

    def _create_portal_query(self, q_value: str, tmpl: Template) -> str:
        # The value should be a URL
        url = q_value
        q_id = q_value.split("/")[-1]  # Last component is a unique query ID
        nb = tmpl.render(
            QUERYNAME=q_id,
            QUERYURL=url,
        )
        r_qdir = join("notebooks", "queries")
        qdir = join(os.getenv("HOME"), r_qdir)
        os.makedirs(qdir, exist_ok=True)
        fname = f"portal_{q_id}.ipynb"
        r_fpath = join(r_qdir, fname)
        fpath = join(qdir, fname)
        with open(fpath, "wb") as f:
            f.write(bytes(nb, "utf-8"))
        retval = {
            "status": 200,
            "filename": fname,
            "path": r_fpath,
            "url": join(
                os.environ.get("JUPYTERHUB_SERVICE_PREFIX"), "tree", r_fpath
            ),
            "body": nb,
        }
        return json.dumps(retval)
