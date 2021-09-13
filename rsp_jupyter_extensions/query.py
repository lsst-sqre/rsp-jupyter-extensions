"""
This is a Handler Module with all the individual handlers for LSSTQuery
"""
import json
import nbformat
import os
import shutil

import nbreport.templating as templ

from nbreport.repo import ReportRepo
from notebook.base.handlers import APIHandler
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

# This defines a git repository for each known query_type.

TEMPLATEMAP = {
    "api": {
        "url": "https://github.com/lsst-sqre/lsst-apiquerytemplate",
        "branch": "JL3",
        "subdir": None,
    },
    "squash": {
        "url": "https://github.com/lsst-sqre/squash-bokeh",
        "branch": "JL2",
        "subdir": "template_notebooks/check_astrometry",
    },
}


class Query_handler(APIHandler):
    """
    RSP templated Query Handler.
    """

    @property
    def rubinquery(self):
        return self.settings["rubinquery"]

    def post(self):
        """
        POST a queryID and get back a prepopulated notebook.
        """
        post_data = json.loads(self.request.body.decode("utf-8"))
        # Do The Deed
        query_id = post_data["query_id"]
        query_type = post_data["query_type"]
        self.log.debug("Query_Type: {}".format(query_type))
        self.log.debug("Query_ID: {}".format(query_id))
        result = self._substitute_query(query_type, query_id)
        self.finish(json.dumps(result))

    def _substitute_query(self, query_type, query_id):
        # These are not from a RubinConfig() object; they belong to the
        #  user Python environment
        top = os.environ.get("JUPYTERHUB_SERVICE_PREFIX")
        root = os.environ.get("HOME")
        dir_name = self._get_dirname(query_type, query_id)
        fpath = "notebooks/queries/" + dir_name
        rpath = root + "/" + fpath
        os.makedirs(rpath, exist_ok=True)
        rfilename = rpath + "/query.ipynb"
        jfilename = top + "/tree/" + fpath + "/query.ipynb"
        retval = {
            "status": 404,
            "filename": rfilename,
            "path": fpath + "/query.ipynb",
            "url": jfilename,
            "body": None,
        }
        if os.path.exists(rfilename):
            with open(rfilename, "rb") as f:
                nb = f.read().decode("utf-8")
        else:
            # We need to create the file from template
            try:
                nb = self._render_from_template(query_type, query_id, fpath)
                nbformat.write(nb, rfilename)
            except ValueError as exc:
                self.log.error("Render error: {}".format(exc))
        if nb:
            retval["status"] = 200
            retval["body"] = nb
        return retval

    def _render_from_template(self, query_type, query_id, fpath):
        template_map = TEMPLATEMAP.get(query_type)
        if not template_map:
            raise ValueError(
                "No template for query type '{}'!".format(query_type)
            )
        template_url = template_map.get("url")
        branch = template_map.get("branch") or "master"
        subdir = template_map.get("subdir")
        if not template_url:
            raise ValueError(
                "No template URL for query type '{}'!".format(query_type)
            )
        repo = None
        nb = None
        extra_context = self._get_extra_context(query_type, query_id)
        purl = urlparse(template_url)
        if not purl.netloc:
            # If there is no netloc, assume that the repository is already
            #  checked out to the given location
            repo = ReportRepo(purl.path)
            nb = self._render_notebook(repo, extra_context)
        else:
            with TemporaryDirectory() as td:
                repo = ReportRepo.git_clone(
                    template_url,
                    checkout=branch,
                    subdir=subdir,
                    clone_base_dir=td,
                )
                self._copy_assets(repo, fpath)
                nb = self._render_notebook(repo, extra_context)
        return nb

    def _copy_assets(self, repo, fpath):
        assets = repo.asset_paths
        rdir = repo.dirname
        for a in assets:
            a_rpath = os.path.relpath(a, rdir)
            a_rdir = os.path.dirname(a_rpath)
            d_dir = fpath + "/" + a_rdir
            os.makedirs(d_dir, exist_ok=True)
            shutil.copy2(a, d_dir)

    def _render_notebook(self, repo, extra_context):
        context = templ.load_template_environment(
            repo.context_path, extra_context=extra_context
        )
        nb = repo.open_notebook()
        rendered_notebook = templ.render_notebook(nb, *context)
        return rendered_notebook

    def _get_dirname(self, query_type, query_id):
        self.log.debug(
            "Query Type: {} | Query ID: {}".format(query_id, query_type)
        )
        qn = query_id
        ul = urlparse(query_id)
        self.log.debug("Parsed Query ID: {}".format(ul))
        if ul.netloc:
            qn = ul.path
        qn = qn.split("/")[-1]
        if not qn:
            qn = "q"
        dir_name = "query-" + query_type + "-" + qn
        self.log.debug("Fname: {}".format(dir_name))
        return dir_name

    def _get_extra_context(self, query_type, query_id):
        context = {}
        if query_type == "api":
            context = {"query_url": query_id}
        elif query_type == "squash":
            context = {"ci_id": query_id}
        else:
            pass
        return context
