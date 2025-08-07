"""Handler Module to provide an endpoint for notebook execution."""

import json
from traceback import format_exception

import nbconvert
import nbformat
import tornado
from jupyter_server.base.handlers import APIHandler
from nbconvert.preprocessors import CellExecutionError

NBFORMAT_VERSION = 4


class ExecutionHandler(APIHandler):
    """RSP templated Execution Handler."""

    @property
    def rubinexecution(self) -> dict[str, str]:
        return self.settings["rubinexecution"]

    @tornado.web.authenticated
    def post(self) -> None:
        """Handle ``POST /rubin/execution``.

        This handler executes a notebook, and returns the rendered notebook,
        along with any resources and errors that occurred during execution.

        **Request body.**
        The request body can take two forms:
        1. A string containing the text of an ipynb file.
        2. A JSON-encoded dict containing a ``notebook`` key (the ipynb as a
           string) and a ``resources`` key (a JSON-encoded dict of resources).
           The second form is used less often, but is useful for passing
           resources to the notebook that are not part of the notebook itself.

        **Request headers.**
        Set the ``X-Kernel-Name`` header to the name of the kernel to use for
        execution.
        """
        input_str = self.request.body.decode("utf-8")
        kernel_name = self.request.headers.get("X-Kernel-Name", None)
        # Do The Deed
        output_str = self._execute_nb(
            input_str=input_str, kernel_name=kernel_name
        )
        self.write(output_str)

    def _execute_nb(self, *, input_str: str, kernel_name: str | None) -> str:
        # We will try to decode it as if it were a resource-bearing document.
        #  If that fails, we will assume it to be a bare notebook string.
        #
        # It will return a string which is the JSON representation of
        # an object with the keys "notebook", "resources", and "error"
        #
        # The notebook and resources are the results of execution as far as
        # successfully completed, and "error" is either None (for success)
        # a CellExecutionError where execution failed, or some other kind
        # of Exception (we have seen JSON validation errors on malformed
        # notebooks, for instance).
        try:
            d = json.loads(input_str)
            resources = d["resources"]
            nb_str = d["notebook"]
        except Exception:
            resources = None
            nb_str = input_str
        nb = nbformat.reads(nb_str, NBFORMAT_VERSION)
        if kernel_name is not None:
            executor = nbconvert.preprocessors.ExecutePreprocessor(
                kernel_name=kernel_name
            )
        else:
            # If kernel_name is None, don't set it to avoid TraitError
            executor = nbconvert.preprocessors.ExecutePreprocessor()
        exporter = nbconvert.exporters.NotebookExporter()

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
            # The CellExecutionError is not directly JSON-serializable, so
            # we will just extract the fields from it and return those.
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
        except Exception as exc:
            # Catch a generic exception.  Do our best to format it reasonably.
            (rendered, rendered_resources) = exporter.from_notebook_node(
                executor.nb, resources=executor.resources
            )
            name = exc.__class__.__name__
            tb = "\n".join(format_exception(exc)).strip()
            return json.dumps(
                {
                    "notebook": rendered,
                    "resources": rendered_resources,
                    "error": {
                        "traceback": tb,
                        "ename": name,
                        "evalue": str(exc),
                        "err_msg": tb,
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
