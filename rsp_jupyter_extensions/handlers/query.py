"""Handler Module to provide an endpoint for templated queries."""
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import tornado
import xmltodict
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
        """Get a client to talk to Portal API."""
        super().initialize()
        self._ts_client = RSPClient(base_path="times-square/api/v1/")
        self._tap_client = RSPClient(base_path="/api/tap/")
        self._cachefile = (Path(os.getenv("JUPYTER_SERVER_ROOT", "")) /
                           ".cache" / "queries.json" )
        self._initialize_cache()

    def _initialize_cache(self) -> None:
        """We get a new instance of the class every time the front end
        calls the endpoint.  Once a query has been issued, it is immutable.
        While getting the list of latest queries each time is something we
        cannot avoid, retrieving the text might be--if we already grabbed
        that text, we can just return the value from the cache and avoid
        another trip to TAP.
        """
        if not self._cachefile.is_file():
            self._cache: dict[str, str] = {}
            self._cachefile.parent.mkdir(exist_ok=True, parents=True)
            self._cachefile.write_text(json.dumps(self._cache))
        else:
            self._cache = json.loads(self._cachefile.read_text())

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
        nb = self._get_tap_query_notebook(url)
        fname = (
            Path(os.getenv("JUPYTER_SERVER_ROOT", ""))
            / "notebooks"
            / "queries"
            / f"tap_{q_id}.ipynb"
        )
        await self.refresh_query_history()  # Opportunistic
        return _write_notebook_response(nb, fname)

    def _get_tap_query_notebook(self, url: str) -> str:
        """Ask times-square for a rendered notebook."""
        # These are all constant for this kind of query
        org = "lsst-sqre"
        repo = "nublado-seeds"
        directory = "portal"
        notebook = "query"

        # Since we know the path we don't have to crawl the base github
        # response
        nb_url = f"github/{org}/{repo}/{directory}/{notebook}"

        # The only parameter we have is query_url, which is the TAP query
        # URL
        params = {"query_url": url}

        # Get the endpoint for the rendered URL
        obj = self._ts_client.get(nb_url).json()
        rendered_url = obj["rendered_url"]

        # Retrieve that URL and return the textual response, which is the
        # string representing the rendered notebook "in unicode", which I
        # think means, "a string represented in the default encoding".
        return self._ts_client.get(rendered_url, params=params).text

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
            jobs = await get_query_history(count)
            qtext = self._get_query_text(jobs)
            q_dicts = [ x.dict() for x in qtext ]
            self.write(json.dumps(q_dicts))
        if len(components) == 1 and components[0] != "history":
            query_id = components[0]
            q_fn = await self._create_query(query_id, "tap")
            self.write(q_fn)
            return
        if components[0] == "notebooks" and components[1] == "query_all":
            self.write(await self._generate_query_all_notebook())
            return

    async def refresh_query_history(self, count: int =5) -> None:
        """Get_query_history, but throw away the results.

        The motivation here is that if we are asked to do anything at all,
        if it is an operation that returns a notebook, that's going to shift
        the user's attention anyway, so we might as well get our data fresh
        in hopes of speeding up the next time they actually want to look at
        recent query history.
        """
        jobs = await get_query_history(count)
        self._get_query_text(jobs)

    async def _generate_query_all_notebook(self) -> str:
        # Get this from nublado-seeds, I guess?
        nbobj:dict[str,Any] = {
            "cells": [
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "from lsst.rsp import get_query_history\n",
                        "hist=await get_query_history()\n"
                        "hist"
                    ]
                }
            ],
            "metadata": {
                "kernelspec": {
                    "display_name": "LSST",
                    "name": "lsst"
                },
                "language_info": {
                    "name": ""
                }
            },
            "nbformat": 4,
            "nbformat_minor": 5
        }
        nbobj["cells"][0]["id"] = str(uuid4())
        output=json.dumps(nbobj)
        fname = (
            Path(os.getenv("JUPYTER_SERVER_ROOT", ""))
            / "notebooks"
            / "queries"
            / "tap_query_history.ipynb"
        )
        await self.refresh_query_history()  # Opportunistic
        return _write_notebook_response(output, fname)

    def _get_query_text(self, job_ids: list[str]) -> list[TAPQuery]:
        """For each job ID, get the query text.  This will be returned
        to the UI to be used as a hover tooltip.

        Each time through, we both get results we already have for the
        cache, and update the cache if we get new results.
        """
        retval: list[TAPQuery] = []
        self.log.info(f"Requesting query history for {job_ids}")
        for job in job_ids:
            if job in self._cache:
                retval.append(
                    TAPQuery(jobref=job,text=self._cache[job])
                )
                continue
            resp = self._tap_client.get(f"async/{job}")
            rc = resp.status_code
            if rc != 200:
                self.log.warning(f"job {job} gave status code {rc}")
                continue
            obj = xmltodict.parse(resp.text)
            parms = obj["uws:job"]["uws:parameters"]["uws:parameter"]
            for parm in parms:
                if "@id" in parm and parm["@id"] == "QUERY":
                    qtext = parm.get("#text", None)
                    self.log.info(f"Query text {qtext}")
                    if qtext:
                        tq=TAPQuery(jobref=job,text=qtext)
                        retval.append(tq)
                        self.log.info(f"{job} -> '{qtext}'")
                        self._cache.update({job: qtext})
                        self._cachefile.write_text(json.dumps(self._cache))
                        break
        return retval
