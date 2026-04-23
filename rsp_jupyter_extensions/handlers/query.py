"""Handler Module to provide an endpoint for templated queries."""

import json
import os
from pathlib import Path
from urllib.parse import urljoin

import tornado
import xmltodict
from httpx import ReadTimeout
from jupyter_server.base.handlers import APIHandler

from ..models.query import (
    NotANotebookError,
    TAPQuery,
    UnimplementedQueryResolutionError,
    UnsupportedQueryTypeError,
)
from ._utils import _peel_route, _write_notebook_response
from .clients import RSPClient


class QueryHandler(APIHandler):
    """RSP templated Query Handler."""

    def initialize(self) -> None:
        """Get a client to talk to Times Square and TAP APIs."""
        super().initialize()
        self._home_dir = Path(os.getenv("HOME", ""))
        if "query" not in self.settings:
            self.settings["query"] = {}
        if "cache" not in self.settings["query"]:
            self.settings["query"]["cache"] = {}
        if "client" not in self.settings["query"]:
            self.settings["query"]["client"] = RSPClient(logger=self.log)
        self._rsp_client = self.settings["query"]["client"]
        self._cache = self.settings["query"]["cache"]

    @tornado.web.authenticated
    async def post(self, *args: str, **kwargs: str) -> None:
        """POST receives the query type and the query value as a JSON
        object containing "type" and "value" keys.  Each is a string.

        "type" is currently limited to "tap".

        The interpretation of "value" is query-type dependent.

        For a TAP query, "value" is the URL, or the bare jobref ID (in which
        case known datasets will be searched for the ID), or a string in the
        form of "dataset:jobref_id", referring to that query.

        It will then use the value to resolve the template, and
        construct a filename resolved under $HOME.  If that file
        exists, we will return it, on the grounds that the user has
        done this particular query before and we want to keep any
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
        # A jobref ID is always 16 alphanumeric characters, or, optionally,
        # a dataset name followed by a colon followed by 16 alphanumeric
        # characters. We assume no one will create a dataset name with a
        # slash in it.
        #
        # Therefore: if the query value contains a slash, it's a URL.
        self.log.debug(f"Tap query requested for {q_value}")
        if q_value.find("/") != -1:
            self.log.debug(f"Assuming {q_value} is a URL")
            # This looks like a URL
            # Trim trailing slashes
            q_value = q_value.rstrip("/")
            url = q_value
            slashes = q_value.count("/")
            if slashes == 0:
                # Seriously?  It was just slashes to start with?
                raise UnimplementedQueryResolutionError("")
            q_pieces = q_value.split("/")
            q_id = q_pieces[-1]  # Last component is the jobref ID
            # This ought to be pretty rare; like, if that was a sane
            # URL, it was something like ..../api/tap/async/abcde, and this
            # will end up being "tap".
            q_ds = q_pieces[-3] if slashes > 2 else "unknown"
            url = q_value
        else:
            self.log.debug(f"Resolving jobref_id {q_value}")
            jobref = await self._rsp_client.resolve_jobref_id(q_value)
            q_ds = jobref.dataset
            q_id = jobref.jobref_id
            base_url = jobref.endpoint
            self.log.debug(f"Base URL for {q_ds} is {base_url}")
            url = f"{base_url}/async/{q_id}"
        self.log.debug(f"TAP query URL for {q_value} is {url}")
        fname = (
            self._home_dir / "notebooks" / "queries" / f"{q_ds}_{q_id}.ipynb"
        )
        if fname.is_file():
            self.log.debug(f"File {fname!s} already exists.")
            nb = fname.read_text()
        else:
            nb = await self._get_tap_query_notebook(url)
        await self.refresh_query_history()  # Opportunistic
        self.log.debug(f"Creating file {fname!s}")
        return _write_notebook_response(nb, fname)

    async def _get_ts_query_notebook(
        self,
        org: str,
        repo: str,
        directory: str,
        notebook: str,
        params: dict[str, str],
    ) -> str:
        """Ask times-square for a rendered notebook."""
        path = f"api/v1/github/rendered/{org}/{repo}/{directory}/{notebook}"
        ts_url = await self._rsp_client.get_times_square_url() or ""
        rendered_url = urljoin(ts_url, path)
        self.log.debug(
            f"Requesting rendered notebook from {rendered_url}"
            f" with params: {params}"
        )

        # Retrieve that URL and return the textual response, which is the
        # string representing the rendered notebook "in unicode", which
        # means "a string represented in the default encoding".
        #
        # We do a little sanity check: if what we get back isn't JSON, it
        # definitely isn't a notebook, and we shouldn't write it to the
        # user's space.
        resp = await self._rsp_client.authed_client.get(
            rendered_url, params=params
        )
        self.log.debug(f"GET {resp.url} -> status code {resp.status_code}")
        try:
            _ = json.loads(resp.text)
        except Exception:
            self.log.warning("Response text is not valid JSON")
            raise NotANotebookError(resp.url) from None
        return resp.text

    async def _get_nublado_seeds_notebook(
        self, notebook: str, params: dict[str, str]
    ) -> str:
        """Partially-curried function with invariant parameters filled in."""
        org = os.getenv("NUBLADO_SEEDS_ORG", "lsst-sqre")
        repo = os.getenv("NUBLADO_SEEDS_REPO", "nublado-seeds")
        directory = os.getenv("NUBLADO_SEEDS_DIR", "tap")

        return await self._get_ts_query_notebook(
            org, repo, directory, notebook, params
        )

    async def _get_tap_query_notebook(self, url: str) -> str:
        """Even-more-curried helper function for TAP query notebook."""
        notebook = "query"
        # The only parameter we have is query_url, which is the TAP query
        # URL
        params = {"query_url": url}

        return await self._get_nublado_seeds_notebook(notebook, params)

    async def _get_query_all_notebook(self) -> str:
        """Even-more-curried helper function for TAP history notebook."""
        notebook = "history"
        params: dict[str, str] = {}
        return await self._get_nublado_seeds_notebook(notebook, params)

    @tornado.web.authenticated
    async def get(self, *args: str, **kwargs: str) -> None:
        #
        # The only supported querytype for now is "tap"
        #
        # GET .../<qtype>/<id> will act as if we'd posted a query with
        #     qytpe and id; id should be in the form dataset:query_id
        # GET .../<qtype>/history/<n> will request the last n queries of
        #     that type for each dataset.
        # GET .../<qtype>/notebooks/query_all will create and open a notebook
        #     that will ask for all queries and yield their jobids.

        path = self.request.path
        stem = "/rubin/queries"

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
            retries = 0
            while True:
                try:
                    jobs = await self._rsp_client.get_query_history(count)
                    break
                except ReadTimeout:
                    if retries < 3:
                        retries += 1
                    else:
                        # Failed three times.  Give up.
                        self.write(json.dumps({}))
                        return
            qdict = await self._get_query_text_list(jobs)
            # This is a change from previous versions: we return a dict of
            # dataset-name to query-history-list for that dataset
            q_list = {x: [y.model_dump() for y in qdict[x]] for x in qdict}
            self.write(json.dumps(q_list))
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
            jobs = await self._rsp_client.get_query_history(count)
            await self._get_query_text_list(jobs)
        except ReadTimeout:
            # get_query_history can be weirdly slow
            pass

    async def _generate_query_all_notebook(self) -> str:
        output = await self._get_query_all_notebook()
        fname = (
            self._home_dir
            / "notebooks"
            / "queries"
            / "tap_query_history.ipynb"
        )
        await self.refresh_query_history()  # Opportunistic
        return _write_notebook_response(output, fname)

    async def _get_query_text_list(
        self, job_ids: dict[str, list[dict[str, str]]]
    ) -> dict[str, list[TAPQuery]]:
        """For each job ID, get the query text.  This will be returned
        to the UI to be used as a hover tooltip.

        Each time through, we both get results we already have for the
        cache, and update the cache if we get new results.
        """
        retval: dict[str, list[TAPQuery]] = {}
        self.log.info(f"Requesting query history for {job_ids}")
        for dataset, jobs in job_ids.items():
            for job in jobs:
                try:
                    qtext: TAPQuery | None = None
                    jobkey = ""
                    jobkey = f"{dataset}:{job['@id']}"
                    qtext = await self._get_query_text_job(jobkey)
                except Exception:
                    if jobkey:
                        self.log.exception(
                            f"job {jobkey} text retrieval failed"
                        )
                    else:
                        self.log.exception(
                            "text retrieval failed for unknown job"
                        )
                if dataset not in retval and qtext:
                    retval[dataset] = []
                if qtext:
                    retval[dataset].append(qtext)
        return retval

    async def _get_query_text_job(self, job: str) -> TAPQuery:
        if job in self._cache:
            return TAPQuery(jobref=job, text=self._cache[job])
        jobref = await self._rsp_client.resolve_jobref_id(job)
        self.log.debug(f"{job} -> {jobref}")
        resp = await self._rsp_client.authed_client.get(
            f"{jobref.endpoint}/async/{jobref.jobref_id}"
        )
        resp.raise_for_status()
        # If we didn't get a 200, resp.text probably won't parse, and
        # we will raise that.
        #
        # This could be done with pyvo, but it's really not any easier,
        # because you still have to step through each parameter.
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
                    return tq
        raise RuntimeError(f"Job {job} did not have associated query text")
