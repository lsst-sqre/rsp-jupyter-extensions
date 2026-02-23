"""Handler Module to provide an endpoint for templated queries."""

import asyncio
import json
import os
import urllib
from pathlib import Path
from typing import Any, NoReturn

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
        self._ts_client: httpx.AsyncClient | None = None
        self._dataset_tap_client: dict[str, httpx.AsyncClient] = {}
        self._home = Path(os.environ["HOME"])
        self._cachefile = self._home / ".cache" / "queries.json"
        self._token = _get_access_token()
        self._former_default_tap_client: httpx.AsyncClient | None = None
        self._former_default_dataset: str | None = None
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
        if self._ts_client:
            # We've already set it (although since we get a new instance
            # of this handler with every request...)
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
        if self._dataset_tap_client:
            # We've already set it.  This is a route handler; we will
            # reinitialize on every request anyway.
            return
        datasets = await self._discovery.datasets()
        self.log.debug(f"Discovered datasets: {datasets}")
        for ds in datasets:
            self.log.debug(f"Getting TAP client for {ds}")
            url = await self._discovery.url_for_data("tap", ds)
            if url:
                self._dataset_tap_client[ds] = self._make_client(url)
        await self._set_former_defaults()

    async def _set_former_defaults(self) -> None:
        """Emulate older behavior.

        This heuristic is not very good, but here's the logic.

        We used to just assume that there was one and only one TAP
        endpoint in the RSP.  It was at /api/tap relative to the root.

        This is no longer even remotely true, but we have some tutorial
        notebooks and helper code that assumes that.

        So what we're going to do is: get the list of all TAP services
        whose paths are "/api/tap" and whose hosts match the squareone
        UI hostname.  Pick the first (for basically no reason) and assign
        that as the "default" dataset.

        This very well might be the wrong dataset, but here we encounter
        the problem that there's no way to tell datasets apart (other than
        parsing the actual ADQL) if they're on the same endpoint.  The
        good news is, the endpoint's right, and a query to that endpoint
        will return the correct data.
        """
        if self._discovery is None:
            self.log.warning(
                "Cannot locate squareone without discovery client."
            )
            return
        sq1 = await self._discovery.url_for_ui("squareone")
        if not sq1:
            return
        landing_host = (httpx.URL(sq1)).host
        # The comprehension might be faster, but it gets confusing quickly.
        for ds, client in self._dataset_tap_client.items():
            base_url = client.base_url
            if base_url.path == "/api/tap" and base_url.host == landing_host:
                self._former_default_dataset = ds
                self._former_default_tap_client = client
                break
        if not self._dataset_tap_client:
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

        For a TAP query, "value" is the URL, or a bare jobref ID (in which
        case the former default dataset is assumed), or a string in the
        form of "dataset:jobref_id", referring to that query.

        It will then use the value to resolve the template, and
        construct a filename resolved under $HOME.

        If that file exists, we will return it, on the grounds that
        the user has done this particular query before and we want to
        keep any changes made.  Otherwise we will write a file with
        the query template resolved, so the user can run it to
        retrieve results.
        """
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
        """Create a TAP query from a URL or a jobref ID.

        A jobref ID should be in the form of <dataset>:<id>
        A job ID is always 16 alphanumeric characters.
        Therefore: if the query contains a slash, it's a URL.

        If the jobref does not contain a colon, we assume the
        former default dataset.  This is pretty gross, but currently it's
        what the portal gives you to copy easily.

        I don't know what the portal does with multiple tap backends.
        """
        client: httpx.AsyncClient | None = None
        q_ds: str | None = None
        q_id: str | None = None
        if q_value.find("/") != -1:
            # This looks like a URL
            # Trim trailing slashes
            q_value = q_value.rstrip("/")
            slashes = q_value.count("/")
            if slashes == 0:
                self._unresolvable("Empty URL")
            q_ds = self._get_dataset_for_url(q_value)
            if q_ds is None:
                self._unresolvable(
                    f"Cannot determine plausible dataset for {q_value}"
                )
            q_pieces = q_value.split("/")
            q_id = q_pieces[-1]  # Last component is the jobref ID
            client = self._dataset_tap_client[q_ds]
        # If it contains a colon, it's dataset:jobref_id.
        elif q_value.find(":") != -1:
            q_ds, q_id = q_value.split(":")
            if q_ds not in self._dataset_tap_client:
                self._unresolvable(f"No TAP client for dataset {q_ds}")
            client = self._dataset_tap_client[q_ds]
        else:
            # No colon, so no dataset, so we assume our default tap client.
            if (
                self._former_default_dataset is None
                or self._former_default_tap_client is None
            ):
                self._unresolvable(
                    f"Cannot determine default dataset for {q_value}"
                )
            q_ds = self._former_default_dataset
            client = self._former_default_tap_client
            q_id = q_value
        if not q_ds or not q_id:
            self._unresolvable(
                f"Cannot determine dataset {q_ds} / query id {q_id}"
            )
        if client is None or client.base_url is None:
            # Because of the way we make clients, this will not actually
            # happen.
            self._unresolvable(f"Cannot determine base URL for ds {q_ds}")
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

    def _unresolvable(self, errmsg: str) -> NoReturn:
        """Bail out: a convenience method."""
        self.log.error(errmsg)
        raise UnimplementedQueryResolutionError(errmsg)

    def _get_dataset_for_url(self, url: str) -> str | None:
        """Use Portal-supplied URL to extract a dataset name.

        That URL doesn't (directly) have a dataset name.  We can get *a*
        dataset that you could retrieve via that URL, but since multiple
        datasets can have the same tap endpoint, we can't guarantee that the
        query really matches the dataset we found.
        """
        for ds, client in self._dataset_tap_client.items():
            base_url = str(client.base_url)
            if url.startswith(base_url):
                return ds
        return None

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
        # means "a string represented in the default encoding" (which is
        # UTF-8).
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
        """Even-more-curried helper function for cross-dataset history
        notebook.
        """
        notebook = "all-history"
        params: dict[str, str] = {}
        return await self._get_nublado_seeds_notebook(notebook, params)

    async def _get_query_all_notebook_for_dataset(self, dataset: str) -> str:
        """Even-more-curried helper function for TAP history notebook."""
        notebook = "dataset-history"
        params = {"url": str(self._dataset_tap_client[dataset].base_url)}
        # Remember to update the notebook to take the base_url
        return await self._get_nublado_seeds_notebook(notebook, params)

    @tornado.web.authenticated
    async def get(self, *args: str, **kwargs: str) -> None:
        """Respond to UI Query Menu.

        The only supported querytype for now is "tap"

        GET .../<qtype>/history/<n> will request the last n
         queries across all datasets.
        GET .../<qtype>/history will request the last 5 queries
         across all datasets.

        GET .../<qtype>/query_all will create and open a notebook
         that will ask for all queries across all datasets and
         yield their IDs.

        GET .../<qtype>/<dataset>/<id> will act as if we'd posted
         a query for job <id> to dataset <dataset>.
        GET .../<qtype>/<dataset>/history/<n> will request the last n
         queries for dataset <dataset>.
        GET .../<qtype>/<dataset>/query_all will create and open a notebook
         that will ask for all queries for that dataset and yield their
         job ids.
        """
        await self._initialize_clients()

        path = self.request.path
        stem = "/rubin/query"

        route = _peel_route(path, stem)
        if route is None:
            self._unresolvable(f"Cannot strip '{stem}' from '{path}'")
        route = route.strip("/")  # Remove leading and trailing slashes.
        components = route.split("/")
        if len(components) < 2 or len(components) > 4:
            errmsg = (
                f"Cannot parse query from '{path}' components '{components}'"
            )
            self._unresolvable(errmsg)
        q_type = components[0]
        match q_type:
            case "tap":
                pass
            case _:
                self._unresolvable(f"{q_type} is not a supported query type")
        next_comp = components[1]
        if next_comp == "history":
            await self._history_parse(components[2:])
        elif next_comp == "query_all":
            await self._get_query_all_notebook()
        else:
            await self._tap_route_get(components[1:])

    def _maybe_convert_string(self, inp: str) -> int:
        try:
            return int(inp)
        except Exception as exc:
            self._unresolvable(f"Cannot convert {inp} to int -> {exc!s}")

    async def _history_parse(self, components: list[str]) -> None:
        if not components:
            # Get a notebook to get all history from all datasets
            await self._get_query_all_notebook()
            return
        next_comp = components[0]
        datasets = list(self._dataset_tap_client.keys())
        if next_comp in datasets:
            dataset = next_comp
            await self._history_for_dataset(dataset, components[1:])
            return
        count = self._maybe_convert_string(next_comp)
        await self.get_query_history_all_datasets(count)

    async def _history_for_dataset(
        self, dataset: str, components: list[str]
    ) -> None:
        if not components:
            self.write(
                await self._generate_query_all_notebook_for_dataset(dataset)
            )
            return
        count = self._maybe_convert_string(components[2])
        try:
            jobs = await self.get_query_history_for_dataset(dataset, count)
        except Exception:
            # get_query_history can sometimes be weirdly slow
            self.log.exception("get_query_history failed:")
            self.write(json.dumps([]))
            return
        self.log.debug(f"Jobs found: {jobs}")
        qtext = await self._get_query_text_list([x["@id"] for x in jobs])
        q_dicts = [x.model_dump() for x in qtext]
        self.write(json.dumps(q_dicts))

    async def _tap_route_get(self, components: list[str]) -> None:
        if len(components) < 2 or len(components) > 3:
            self._unresolvable(f"Cannot parse route: {'/'.join(components)}")
        dataset = components[0]
        if len(components) == 3 and components[1] != "history":
            query_id = components[1]
            q_fn = await self._create_query(query_id, "tap")
            self.write(q_fn)
            return
        if components[1] == "notebooks" and components[2] == "query_all":
            self.write(
                await self._generate_query_all_notebook_for_dataset(dataset)
            )
            return

    async def get_query_history_for_dataset(
        self, dataset: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Retrieve last ``limit`` query jobs for dataset.  If limit
        is not specified, or limit < 1, retrieve all query jobs.

        Parameters
        ----------
        dataset
            Dataset to query.
        limit
            Maximum number of query IDs to return.  If limit < 1, return
        all query IDs.

        Returns
        -------
        list[str]
            A list of strings in the format dataset:query_id.
        """
        params = {"last": str(limit)} if limit > 0 else {}
        jobs: list[dict[str, Any]] = []
        client = self._dataset_tap_client.get(dataset)
        if client is None:
            self._unresolvable(f"No TAP client for dataset {dataset}")
        resp = await client.get("async", params=params)
        status = resp.status_code
        self.log.debug(
            f"history query :{dataset} (limit {limit} -> status code {status}"
        )
        if status < 400:
            self.log.debug(f"Getting history for task {dataset}")
            text = resp.text
            self.log.debug(f"Truncated text: {text[:50]}")
            parsed = xmltodict.parse(text, force_list=("uws:jobref",))
            self.log.debug(f"Parsed text: {json.dumps(parsed, indent=2)}")
            history = parsed
        else:
            self.log.warning(
                f"history for dataset {dataset} failed with status {status}"
            )
            return []
        if "uws:jobs" in history:
            if "uws:jobref" in history["uws:jobs"]:
                for entry in history["uws:jobs"]["uws:jobref"]:
                    # Annotate job with dataset name
                    entry["__dataset__"] = dataset
                    self.log.debug(f"job for {dataset} -> {entry}")
                    jobs.append(entry)

        return self._sort_and_truncate(jobs, limit)

    def _sort_and_truncate(
        self, jobs: list[dict[str, Any]], limit: int
    ) -> list[dict[str, Any]]:
        """
        We assume that by the time we get here, we have a list of
        jobrefs with the appropriate structure.

        We might want to put together a Pydantic model for what the
        xmltodict is expected to produce, because the current typing
        is very loose.

        As far as we can tell, uws:creationTime can simply be lexically
        sorted and will produce the proper ordering.  If somehow it is
        missing (it should not be), we assign it the Unix Epoch, which
        will presumably be "older than anything else".  This just gets us
        the jobs sorted by creation time.
        """
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
        return last_limit

    async def get_query_history_all_datasets(
        self, limit: int = 5
    ) -> list[str]:
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
        self.log.debug("Entering get_query_history_all_datasets()")
        params = {"last": str(limit)} if limit > 0 else {}
        jobs: list[dict[str, Any]] = []
        tasks: dict[str, asyncio.Task] = {}
        endpoints: set[str] = set()
        # parallelize it
        async with asyncio.TaskGroup() as tg:
            for dataset, client in self._dataset_tap_client.items():
                base_url = str(client.base_url)
                if base_url in endpoints:
                    # We cannot tell the difference between, say, dp02 and
                    # dp1, if they are both at /api/tap.  So there's no
                    # point in scanning it twice.
                    self.log.debug(
                        f"skipping dataset {dataset} because endpoint"
                        f" {base_url} already queried"
                    )
                    continue
                endpoints.add(base_url)
                tasks[dataset] = tg.create_task(
                    self.get_query_history_for_dataset(dataset, limit)
                )
                self.log.debug(
                    f"task created: dataset {dataset}, params {params}"
                )

        # The async with implicitly waits for all the tasks at context
        # manager exit.
        # Chew through task results and add each jobref to the history dict.
        for task in tasks.values():
            jobs.extend(task.result())

        truncated = self._sort_and_truncate(jobs, limit)
        return self._summarize_jobs(truncated)

    def _summarize_jobs(self, jobs: list[dict[str, Any]]) -> list[str]:
        # Return the job list as dataset:query_id; this is where we use
        # the annotation we just stuck to each job.
        return [f"{x['__dataset__']}:{x['@id']}" for x in jobs]

    async def refresh_query_history(self, count: int = 5) -> None:
        """Get_query_history, but throw away the results.

        The motivation here is that if we are asked to do anything at all,
        if it is an operation that returns a notebook, that's going to shift
        the user's attention anyway, so we might as well get our data fresh
        in hopes of speeding up the next time they actually want to look at
        recent query history.
        """
        try:
            jobs = await self.get_query_history_all_datasets(count)
            await self._get_query_text_list(jobs)
        except Exception:
            # get_query_history can sometimes be weirdly slow
            self.log.exception("Opportunistic query refresh failed")

    async def _generate_query_all_notebook_for_dataset(
        self, dataset: str
    ) -> str:
        output = await self._get_query_all_notebook_for_dataset(dataset)
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
        # If there is no colon, we guess
        if job.find(":") == -1:
            if self._former_default_tap_client is None:
                raise MissingClientError(
                    f"No former default client to handle job {job}"
                )
            client = self._former_default_tap_client
            job_id = job
            ds = self._former_default_dataset
            self.log.debug(f"Assuming dataset {ds} for job {job}")
        else:
            # We have a dataset, and presumably a matching client.
            ds, job_id = job.split(":")
            maybe_client = self._dataset_tap_client.get(ds)
            if not maybe_client:
                raise MissingClientError(f"No client for dataset '{ds}'")
            client = maybe_client
        self.log.debug(
            f"Getting job {job} with client for ds {ds}"
            f" with base URL {client.base_url!s}"
        )
        resp = await client.get(f"async/{job_id}")
        resp.raise_for_status()
        # If we didn't get a 200, resp.text probably won't parse, and
        # we will raise that.
        text = resp.text
        self.log.debug(f"query {job_id} truncated text: {text[:50]}")
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
