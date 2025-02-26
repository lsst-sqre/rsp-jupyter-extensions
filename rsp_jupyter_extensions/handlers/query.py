"""Handler Module to provide an endpoint for templated queries."""

import json
import os
from pathlib import Path

import tornado
import xmltodict
from httpx import ReadTimeout
from jupyter_server.base.handlers import APIHandler
from lsst.rsp import get_query_history

from ..models.query import (
    TAPQuery,
    UnimplementedQueryResolutionError,
    UnsupportedQueryTypeError,
)
from ._rspclient import RSPClient
from ._utils import _peel_route, _write_notebook_response


class QueryHandler(APIHandler):
    """RSP templated Query Handler."""

    def initialize(self) -> None:
        """Get a client to talk to Times Square and TAP APIs."""
        super().initialize()
        self._ts_client = RSPClient(base_path="times-square/api/v1/")
        self._tap_client = RSPClient(base_path="/api/tap/")
        self._root_dir = Path(os.getenv("JUPYTER_SERVER_ROOT", ""))
        self._cachefile = self._root_dir / ".cache" / "queries.json"
        self._initialize_cache()

    def _initialize_cache(self) -> None:
        """We get a new instance of the class every time the front end
        calls the endpoint.  Once a query has been issued, it is immutable.
        While getting the list of latest queries each time is something we
        cannot avoid, retrieving the text might be--if we already grabbed
        that text, we can just return the value from the cache and avoid
        another trip to TAP.
        """
        if self._cachefile.is_file():
            try:
                self._cache = json.loads(self._cachefile.read_text())
            except json.decoder.JSONDecodeError:
                pass  # Can't read it; invalidate and start over.
            else:
                return
        # Invalidate cache.
        self._cache = {}
        self._cachefile.parent.mkdir(exist_ok=True, parents=True)
        self._cachefile.write_text(json.dumps(self._cache))

    @property
    def rubinquery(self) -> dict[str, str]:
        """Rubin query params."""
        return self.settings["rubinquery"]

    @tornado.web.authenticated
    async def post(self, *args: str, **kwargs: str) -> None:
        """POST receives the query type and the query value as a JSON
        object containing "type" and "value" keys.  Each is a string.

        "type" is currently limited to "tap".

        For a TAP query, "value" is the URL or jobref ID referring to that
        query.   The interpretation of "value" is query-type dependent.

        It will then use the value to resolve the template, and
        construct a filename resolved under $JUPYTER_SERVER_ROOT
        (self._rootdir, and in the RSP, the same as $HOME).  If that
        file exists, we will return it, on the grounds that the user
        has done this particular query before and we want to keep any
        changes made.  Otherwise we will write a file with the query
        template resolved, so the user can run it to retrieve results.
        """
        input_str = self.request.body.decode("utf-8")
        input_document = json.loads(input_str)
        q_type = input_document["type"]
        q_value = input_document["value"]
        q_fn = await self._create_query(q_value, q_type)
        self.write(q_fn)

    async def _create_query(self, q_value: str, q_type: str) -> str:
        match q_type:
            case "tap":
                return await self._create_tap_query(q_value)
            case _:
                raise UnsupportedQueryTypeError(
                    f"{q_type} is not a supported query type"
                )

    async def _create_tap_query(self, q_value: str) -> str:
        # The value should be a URL or a jobref ID
        this_rsp = os.getenv("EXTERNAL_INSTANCE_URL", "not-an-rsp")
        if q_value.startswith(this_rsp):
            # This looks like a URL
            url = q_value
            q_id = q_value.split("/")[-1]  # Last component is the jobref ID
        else:
            # It's a raw jobref ID
            url = f"{this_rsp}/api/tap/async/{q_value}"
            q_id = q_value
        fname = self._root_dir / "notebooks" / "queries" / f"tap_{q_id}.ipynb"
        if fname.is_file():
            nb = fname.read_text()
        else:
            nb = self._get_tap_query_notebook(url)
        await self.refresh_query_history()  # Opportunistic
        return _write_notebook_response(nb, fname)

    def _get_ts_query_notebook(
        self,
        org: str,
        repo: str,
        directory: str,
        notebook: str,
        params: dict[str, str],
    ) -> str:
        """Ask times-square for a rendered notebook."""
        rendered_url = f"github/rendered/{org}/{repo}/{directory}/{notebook}"

        # Retrieve that URL and return the textual response, which is the
        # string representing the rendered notebook "in unicode", which
        # means "a string represented in the default encoding".
        return self._ts_client.get(rendered_url, params=params).text

    def _get_nublado_seeds_notebook(
        self, notebook: str, params: dict[str, str]
    ) -> str:
        """Partially-curried function with invariant parameters filled in."""
        org = os.getenv("NUBLADO_SEEDS_ORG", "lsst-sqre")
        repo = os.getenv("NUBLADO_SEEDS_REPO", "nublado-seeds")
        directory = os.getenv("NUBLADO_SEEDS_DIR", "tap")

        return self._get_ts_query_notebook(
            org, repo, directory, notebook, params
        )

    def _get_tap_query_notebook(self, url: str) -> str:
        """Even-more-curried helper function for TAP query notebook."""
        notebook = "query"
        # The only parameter we have is query_url, which is the TAP query
        # URL
        params = {"query_url": url}

        return self._get_nublado_seeds_notebook(notebook, params)

    def _get_query_all_notebook(self) -> str:
        """Even-more-curried helper function for TAP history notebook."""
        notebook = "history"
        params: dict[str, str] = {}
        return self._get_nublado_seeds_notebook(notebook, params)

    @tornado.web.authenticated
    async def get(self, *args: str, **kwargs: str) -> None:
        #
        # The only supported querytype for now is "tap"
        #
        # GET .../<qtype>/<id> will act as if we'd posted a query with
        #     qytpe and id
        # GET .../<qtype>/history/<n> will request the last n queries of
        #     that type.
        # GET .../<qtype>/notebooks/query_all will create and open a notebook
        #     that will ask for all queries and yield their jobids.

        path = self.request.path
        stem = "/rubin/query"

        route = _peel_route(path, stem)
        if route is None:
            self.log.warning(f"Cannot strip '{stem}' from '{path}'")
            raise UnimplementedQueryResolutionError(path)
        route = route.strip("/")  # Remove leading and trailing slashes.
        components = route.split("/")
        if len(components) < 2 or len(components) > 3:
            self.log.warning(
                f"Cannot parse query from '{path}' components '{components}'"
            )
            raise UnimplementedQueryResolutionError(path)
        q_type = components[0]
        match q_type:
            case "tap":
                await self._tap_route_get(components[1:])
            case _:
                raise UnsupportedQueryTypeError(
                    f"{q_type} is not a supported query type"
                )

    async def _tap_route_get(self, components: list[str]) -> None:
        if components[0] == "history":
            if len(components) == 1:
                self.write(await self._generate_query_all_notebook())
                return
            s_count = components[1]
            try:
                count = int(s_count)
            except ValueError as exc:
                raise UnimplementedQueryResolutionError(
                    f"{self.request.path} -> {exc!s}"
                ) from exc
            try:
                jobs = await get_query_history(count)
            except ReadTimeout:
                # get_query_history can be weirdly slow
                self.write(json.dumps([]))
                return
            qtext = self._get_query_text_list(jobs)
            q_dicts = [x.model_dump() for x in qtext]
            self.write(json.dumps(q_dicts))
        if len(components) == 1 and components[0] != "history":
            query_id = components[0]
            q_fn = await self._create_query(query_id, "tap")
            self.write(q_fn)
            return
        if components[0] == "notebooks" and components[1] == "query_all":
            self.write(await self._generate_query_all_notebook())
            return

    async def refresh_query_history(self, count: int = 5) -> None:
        """Get_query_history, but throw away the results.

        The motivation here is that if we are asked to do anything at all,
        if it is an operation that returns a notebook, that's going to shift
        the user's attention anyway, so we might as well get our data fresh
        in hopes of speeding up the next time they actually want to look at
        recent query history.
        """
        try:
            jobs = await get_query_history(count)
            self._get_query_text_list(jobs)
        except ReadTimeout:
            # get_query_history can be weirdly slow
            pass

    async def _generate_query_all_notebook(self) -> str:
        output = self._get_query_all_notebook()
        fname = (
            self._root_dir
            / "notebooks"
            / "queries"
            / "tap_query_history.ipynb"
        )
        await self.refresh_query_history()  # Opportunistic
        return _write_notebook_response(output, fname)

    def _get_query_text_list(self, job_ids: list[str]) -> list[TAPQuery]:
        """For each job ID, get the query text.  This will be returned
        to the UI to be used as a hover tooltip.

        Each time through, we both get results we already have for the
        cache, and update the cache if we get new results.
        """
        retval: list[TAPQuery] = []
        self.log.info(f"Requesting query history for {job_ids}")
        for job in job_ids:
            try:
                retval.append(self._get_query_text_job(job))
            except Exception:
                self.log.exception(f"job {job} text retrieval failed")
        return retval

    def _get_query_text_job(self, job: str) -> TAPQuery:
        if job in self._cache:
            return TAPQuery(jobref=job, text=self._cache[job])
        resp = self._tap_client.get(f"async/{job}")
        resp.raise_for_status()
        # If we didn't get a 200, resp.text probably won't parse, and
        # we will raise that.
        obj = xmltodict.parse(resp.text)
        try:
            parms = obj["uws:job"]["uws:parameters"]["uws:parameter"]
        except KeyError:
            parms = []
        for parm in parms:
            if "@id" in parm and parm["@id"] == "QUERY":
                qtext = parm.get("#text", None)
                if qtext:
                    tq = TAPQuery(jobref=job, text=qtext)
                    self.log.debug(f"{job} -> '{qtext}'")
                    self._cache.update({job: qtext})
                    self._cachefile.write_text(json.dumps(self._cache))
                    return tq
        raise RuntimeError("Job {job} did not have associated query text")
