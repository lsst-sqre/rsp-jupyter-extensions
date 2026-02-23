"""Handler Module to provide an endpoint for templated queries."""

import asyncio
import json
import os
import urllib
from pathlib import Path
from typing import Any

import httpx
import tornado
import xmltodict
from jupyter_server.base.handlers import APIHandler
from rubin.repertoire import DiscoveryClient

from ..models.query import (
    MissingClientError,
    TAPQuery,
    UnimplementedQueryResolutionError,
    UnsupportedQueryTypeError,
)
from ._utils import (
    _get_access_token,
    _get_config,
    _peel_route,
    _write_notebook_response,
)


class QueryHandler(APIHandler):
    """RSP templated Query Handler."""

    def initialize(self) -> None:
        """Get clients to talk to Times Square and TAP APIs."""
        super().initialize()
        self.log.info("Initializing QueryHandler.")
        self._config = _get_config()
        self._discovery: DiscoveryClient | None = None
        try:
            self._discovery = DiscoveryClient(
                base_url=self._config["repertoire_base_url"]
            )
        except Exception:
            self.log.warning("Cannot initialize discovery client")
        self._default_tap_client: httpx.AsyncClient | None = None
        self._ts_client: httpx.AsyncClient | None = None
        self._dataset_tap_client: dict[str, httpx.AsyncClient] = {}
        self._home = Path(os.environ["HOME"])
        self._cachefile = self._home / ".cache" / "queries.json"
        self._token = _get_access_token()
        self._default_dataset: str | None = None
        self._initialize_cache()
        # We would like to initialize the clients here, but there are
        # sync/async issues with doing so.  Specifically, we will have
        # a running event loop here, but this isn't an async function,
        # even though it really is running asynchronously inside
        # tornado.
        #
        # Thus we're going to cheat a little and see whether the clients
        # are initialized yet whenever we get a GET or POST.

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

    async def _initialize_clients(self) -> None:
        try:
            await self._initialize_ts_client()
            await self._initialize_dataset_tap_clients()
        except Exception:
            # We should catch this rather than blowing up, even though
            # something is badly wrong.
            #
            # If it fails, the query history menu won't populate, and
            # probably you can't get a templated notebook, but that basically
            # means the query menus won't work but should have no effect
            # on the rest of our functionality, so perhaps we shouldn't crash
            # loading the rest of the extension.
            self.log.warning(
                "Initializing query clients failed (continuing anyway):"
            )

    async def _initialize_ts_client(self) -> None:
        if self._discovery is None:
            self.log.warning("Cannot discover times-square endpoint")
            return
        url = await self._discovery.url_for_internal("times-square")
        self.log.debug(f"Times-square URL: {url}")
        if url:
            self._ts_client = self._make_client(url)
        else:
            self.log.warning("Could not get URL for times-square client.")
            self._ts_client = None

    async def _initialize_dataset_tap_clients(self) -> None:
        if self._discovery is None:
            self.log.warning("Cannot discover dataset endpoints")
            return
        datasets = await self._discovery.datasets()
        self.log.debug(f"Discovered datasets: {datasets}")
        for ds in datasets:
            self.log.debug(f"Getting TAP client for {ds}")
            url = await self._discovery.url_for_data("tap", ds)
            if url:
                self._dataset_tap_client[ds] = self._make_client(url)
                if self._default_tap_client is None:
                    self.log.debug(f"Setting default TAP dataset to {ds}")
                    # The first one we find is the "default" tap client.
                    # We use this if dataset is not specified.
                    self._default_tap_client = self._dataset_tap_client[ds]
                    self._default_dataset = ds
        if self._default_dataset is None:
            self.log.warning("Failed to discover any datasets")

    def _make_client(self, url: str) -> httpx.AsyncClient:
        headers = {
            "Authorization": f"Bearer {self._token}",
        }
        self.log.debug(f"Creating client for {url}")
        return httpx.AsyncClient(
            headers=headers, base_url=url, follow_redirects=True
        )

    @tornado.web.authenticated
    async def post(self, *args: str, **kwargs: str) -> None:
        """POST receives the query type and the query value as a JSON
        object containing "type" and "value" keys.  Each is a string.

        "type" is currently limited to "tap".

        The interpretation of "value" is query-type dependent.

        For a TAP query, "value" is the URL, or the jobref ID (in which
        case the first dataset we discovered is assumed), or a string in the
        form of "dataset:jobref_id", referring to that query.

        It will then use the value to resolve the template, and
        construct a filename resolved under $HOME.

        If that file exists, we will return it, on the grounds that
        the user has done this particular query before and we want to
        keep any changes made.  Otherwise we will write a file with
        the query template resolved, so the user can run it to
        retrieve results.
        """
        if self._default_dataset is None:
            await self._initialize_clients()

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
        # A jobref is always 16 alphanumeric characters.
        # Therefore: if it contains a slash, it's a URL
        if self._discovery is None:
            self.log.warning("Cannot create TAP query")
            return ""
        client: httpx.AsyncClient | None = None
        if q_value.find("/") != -1:
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
        # If it contains a colon, it's dataset:jobref_id.
        elif q_value.find(":") != -1:
            q_ds, q_id = q_value.split(":")
            if q_ds not in self._dataset_tap_client:
                errstr = f"No TAP client for dataset {q_ds}"
                self.log.error(errstr)
                raise UnimplementedQueryResolutionError(errstr)
            client = self._dataset_tap_client[q_ds]
        else:
            # No colon, so no dataset, so we assume our default tap client.
            if (
                self._default_dataset is None
                or self._default_tap_client is None
            ):
                errstr = f"Cannot determine default dataset for {q_value}"
                self.log.error(errstr)
                raise UnimplementedQueryResolutionError(errstr)
            q_ds = self._default_dataset
            client = self._default_tap_client
            q_id = q_value
        if client is None or client.base_url is None:
            # Because of the way we make clients, this will not actually
            # happen.
            errstr = f"Cannot determine base URL for ds {q_ds}"
            self.log.error(errstr)
            raise UnimplementedQueryResolutionError(errstr)
        base_url = str(client.base_url)
        self.log.debug(
            f"Extracted base URL {base_url} from TAP client for {q_ds}"
        )
        q_url = f"/async/{q_id}"
        url = urllib.parse.urljoin(base_url, q_url)
        fname = self._home / "notebooks" / "queries" / f"{q_ds}_{q_id}.ipynb"
        if fname.is_file():
            nb = fname.read_text()
        else:
            nb = await self._get_tap_query_notebook(url)
        await self.refresh_query_history()  # Opportunistic
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
        rendered_url = f"github/rendered/{org}/{repo}/{directory}/{notebook}"

        # Retrieve that URL and return the textual response, which is the
        # string representing the rendered notebook "in unicode", which
        # means "a string represented in the default encoding".
        if self._ts_client is None:
            raise MissingClientError("No client for times-square")
        return (await self._ts_client.get(rendered_url, params=params)).text

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
        #     qtype and id
        # GET .../<qtype>/history/<n> will request the last n queries of
        #     that type.
        # GET .../<qtype>/notebooks/query_all will create and open a notebook
        #     that will ask for all queries and yield their jobids.
        if self._default_dataset is None:
            await self._initialize_clients()

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
                jobs = await self.get_query_history(count)
            except Exception:
                # get_query_history can sometimes be weirdly slow
                self.log.exception("get_query_history failed:")
                self.write(json.dumps([]))
                return
            self.log.debug(f"Jobs found: {jobs}")
            qtext = await self._get_query_text_list(jobs)
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

    async def get_query_history(self, limit: int = 5) -> list[str]:
        """Retrieve last ``limit`` query jobref ids.  If limit is not
        specified, or limit<1, retrieve all query jobref ids.

        Parameters
        ----------
        limit
            Maximum number of query IDs to return.  If limit < 1, return
        all query IDs.

        Returns
        -------
        list[str]
            A list of strings in the format dataset:query_id.

        Notes
        -----
        This formerly assumed the TAP endpoint was at "/api/tap", but now it
        relies on service discovery to find datasets.

        Because we are looking for the last ``limit`` jobref IDs, we must
        retrieve that many from each endpoint, and then sort by query date,
        and then truncate our list to size ``limit``.

        The strings returned will be in the format dataset:query_id; the
        caller must then check for a colon in the value, and use the
        dataset to choose the appropriate TAP client to send the actual
        query to.

        For backwards compatibility, we must assume that if the query
        string does not contain a colon, we mean to use "/api/tap".
        Fortunately, thus far, service discovery in that case would find
        (as of 2 March 2026) the dp1 client, which actually is at "/api/tap",
        and, as the most recent dataset, is the likeliest to be what the
        user meant anyway.

        We expect that by the time the number of datasets gets confusing,
        there will be little-to-no usage of old-style no-dataset query
        ids.
        """
        self.log.debug("Entering get_query_history()")
        params = {"last": str(limit)} if limit > 0 else {}
        history: dict[str, Any] = {}
        jobs: list[dict[str, Any]] = []
        tasks: dict[str, asyncio.Task] = {}
        # parallelize it
        async with asyncio.TaskGroup() as tg:
            for dataset, client in self._dataset_tap_client.items():
                tasks[dataset] = tg.create_task(
                    client.get("async", params=params)
                )
                self.log.debug(
                    f"task created: dataset {dataset}, params {params}"
                )
        # The async with implicitly waits for all the tasks at context
        # manager exit.
        # Chew through task results and add each jobref to the history dict.
        for dataset, task in tasks.items():
            resp = task.result()
            status = resp.status_code
            self.log.debug(f"task: {dataset} -> status code {status}")
            if status < 400:
                self.log.debug(f"Getting history for task {dataset}")
                history[dataset] = xmltodict.parse(
                    resp.text, force_list=("uws:jobref",)
                )
            else:
                self.log.warning(
                    f"Job list request for dataset {dataset} failed"
                    f" with status {status}"
                )
        # Attach a dataset name to each job.
        for dataset, history_ds in history.items():
            if "uws: jobs" in history_ds:
                if "uws:jobref" in history_ds["uws:jobs"]:
                    for entry in history_ds["uws:jobs"]["uws:jobref"]:
                        # Annotate job with dataset name
                        entry["__dataset__"] = dataset
                        self.log.debug(f"job for {dataset} -> {entry}")
                        jobs.append(entry)
        # As far as we can tell, uws:creationTime can simply be lexically
        # sorted and will produce the proper ordering.  If somehow it is
        # missing (it should not be), we assign it the Unix Epoch, which
        # will presumably be "older than anything else".  This just gets us
        # the jobs sorted by creation time.
        jobs.sort(
            key=lambda x: x.get(
                "uws:creationTime", "1970-01-01T00:00:00.000Z"
            ),
            reverse=True,
        )
        self.log.debug(
            f"job ids: {[(x['__dataset__'], x['@id']) for x in jobs]}"
        )
        # Finally, trim list to limit size if there is one.
        last_limit = jobs[:limit] if limit > 0 else jobs
        self.log.debug(f"Truncated jobs: {last_limit}")
        # Return the list as dataset:query_id; this is where we use
        # the annotation we just stuck to each job.
        return [f"{x['__dataset__']}:{x['@id']}" for x in last_limit]

    async def refresh_query_history(self, count: int = 5) -> None:
        """Get_query_history, but throw away the results.

        The motivation here is that if we are asked to do anything at all,
        if it is an operation that returns a notebook, that's going to shift
        the user's attention anyway, so we might as well get our data fresh
        in hopes of speeding up the next time they actually want to look at
        recent query history.
        """
        try:
            jobs = await self.get_query_history(count)
            await self._get_query_text_list(jobs)
        except Exception:
            # get_query_history can sometimes be weirdly slow
            self.log.exception("Opportunistic query refresh failed")

    async def _generate_query_all_notebook(self) -> str:
        output = await self._get_query_all_notebook()
        fname = (
            self._home / "notebooks" / "queries" / "tap_query_history.ipynb"
        )
        await self.refresh_query_history()  # Opportunistic
        return _write_notebook_response(output, fname)

    async def _get_query_text_list(self, job_ids: list[str]) -> list[TAPQuery]:
        """For each job ID, get the query text.  This will be returned
        to the UI to be used as a hover tooltip.

        Each time through, we both get results we already have for the
        cache, and update the cache if we get new results.
        """
        retval: list[TAPQuery] = []
        self.log.info(f"Requesting query history for {job_ids}")
        for job in job_ids:
            try:
                retval.append(await self._get_query_text_job(job))
            except Exception:
                self.log.exception(f"job {job} text retrieval failed")
        return retval

    async def _get_query_text_job(self, job: str) -> TAPQuery:
        if job in self._cache:
            return TAPQuery(jobref=job, text=self._cache[job])
        # If there is no colon, it's whatever is behind /api/tap.
        if job.find(":") == -1:
            if self._default_tap_client is None:
                raise MissingClientError(
                    f"No default client to handle job {job}"
                )
            self.log.debug(
                f"Getting job {job} with client for ds {self._default_dataset}"
                f" with base URL {self._default_tap_client.base_url!s}"
            )
            resp = await self._default_tap_client.get(f"/async/{job}")
        else:
            # We have a dataset, and presumably a matching client.
            ds, job_id = job.split(":")
            client = self._dataset_tap_client.get(ds)
            if not client:
                raise MissingClientError(f"No client for dataset '{ds}'")
            self.log.debug(
                f"Getting job {job} with client for ds {ds}"
                f" with base URL {client.base_url!s}"
            )
            resp = await client.get(f"async/{job_id}")
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
