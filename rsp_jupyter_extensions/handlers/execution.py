"""
This is a Handler Module to provide an endpoint for notebook execution.
"""
import json
from typing import Dict

import nbconvert
import nbformat
import tornado

from jupyter_server.base.handlers import JupyterHandler
from nbconvert.preprocessors import CellExecutionError

NBFORMAT_VERSION = 4


class Execution_handler(JupyterHandler):
    """
    RSP templated Execution Handler.
    """

    @property
    def rubinexecution(self) -> Dict[str, str]:
        return self.settings["rubinexecution"]

    @tornado.web.authenticated
    def post(self) -> None:
        """
        POST the contents of a notebook and get back the rendered,
        executed notebook.

        There are two supported formats.  The first is simply the text
        of an ipynb file.  This is expected to be the common use case.

        The second is a JSON representation of a dict containting a
        notebook and associated resources; the notebook contents (a string
        containing an ipynb file) will be in the "notebook" key and
        the resources will be a string in the key "resources" representing
        a JSON-encoded dict).
        """
        input_str = self.request.body.decode("utf-8")
        # Do The Deed
        output_str = self._execute_nb(input_str)
        self.write(output_str)

    def _execute_nb(self, input_str: str) -> str:
        # We will try to decode it as if it were a resource-bearing document.
        #  If that fails, we will assume it to be a bare notebook string.
        #
        # It will return a string which is the JSON representation of
        # an object with the keys "notebook", "resources", and "error"
        #
        # The notebook and resources are the results of execution as far as
        # successfully completed, and "error" is either None (for success)
        # or a CellExecutionError where execution failed.
        try:
            d = json.loads(input_str)
            resources = d["resources"]
            nb_str = d["notebook"]
        except Exception:
            resources = None
            nb_str = input_str
        nb = nbformat.reads(nb_str, NBFORMAT_VERSION)
        executor = nbconvert.preprocessors.ExecutePreprocessor()
        exporter = nbconvert.exporters.NotebookExporter()

        # cf https://github.com/jupyter/nbconvert/blob/\
        #    a1fec27fec84514e83780d524766d9f74e4bb2e3/nbconvert/\
        #    preprocessors/execute.py#L101
        #
        # If preprocess errors out, executor.nb and executor.resources
        # will be in their partially-completed state, so we don't need to
        # bother with setting up the cell-by-cell execution context
        # ourselves, just catch the error, and return the fields from the
        # executor.
        #
        try:
            executor.preprocess(nb, resources=resources)
        except CellExecutionError as exc:
            (rendered, rendered_resources) = exporter.from_notebook_node(
                executor.nb, resources=executor.resources
            )
            # The Exception is not directly JSON-serializable, so we will
            # just extract the fields from it and return those.
            return json.dumps(
                {
                    "notebook": rendered,
                    "resources": rendered_resources,
                    "error": {
                        "traceback": exc.traceback,
                        "ename": exc.ename,
                        "evalue": exc.evalue,
                        "err_msg": str(exc),
                    },
                }
            )
        # Run succeeded, so nb and resources have been updated in place
        (rendered, rendered_resources) = exporter.from_notebook_node(
            nb, resources=resources
        )
        return json.dumps(
            {
                "notebook": rendered,
                "resources": rendered_resources,
                "error": None,
            }
        )
