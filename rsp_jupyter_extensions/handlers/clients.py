"""Discovery and TAP clients used by the query extension and others.

Used to encapsulate the queries we need to make to other RSP services.
"""

import asyncio
import logging
import os
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

import xmltodict
from httpx import AsyncClient
from rubin.repertoire import DiscoveryClient

from ..exceptions import (
    ClientError,
    ConfigError,
    TokenNotAvailableError,
    UnknownDatasetError,
)
from ..models.config import RSPConfig
from ..models.serviceinfo import ServiceInfo
from .config_generator import ConfigGenerator


@dataclass
class JobRef:
    """Convenience class holding dataset name, jobref ID, and endpoint to
    access that dataset.
    """

    dataset: str
    jobref_id: str
    endpoint: str


class RSPClient:
    """Convenience class to make accessing RSP services easy.

    It includes a discovery client for finding services and datasets,
    an anonymous client for use where we don't need to send a token
    (such as discovery), and an authenticated client for those cases where
    we do need to send a token (such as TAP or Times Square).

    It also includes convenience methods for finding commonly-used endpoints.

    It aggressively caches whatever it can in order to minimize network calls.

    Parameters
    ----------
    discovery_client
        DiscoveryClient to use (optional, created if not specified)
    anonymous_client
        Client for anonymous access to RSP services (optional, created if
        not specified)
    authed_client
        Client for authenticated access to RSP services (optional, created
        if not specified)
    config
        RSP instance configuration (optional, discovered on demand if not
        specified)
    repertoire_url
        URL for Repertoire discovery endpoint (optional, taken from
        $REPERTOIRE_URL if not specified)
    logger
        Logger to use (optional, created if not specified)
    """

    def __init__(
        self,
        discovery_client: DiscoveryClient | None = None,
        anonymous_client: AsyncClient | None = None,
        authed_client: AsyncClient | None = None,
        config: RSPConfig | None = None,
        repertoire_url: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if logger is None:
            logger = logging.getLogger(__name__)
        self._logger = logger
        if anonymous_client is None:
            anonymous_client = AsyncClient(
                headers={"Content-Type": "application/json"}
            )
        self.anonymous_client = anonymous_client
        self.authed_client = authed_client
        self._config = config
        if discovery_client is None:
            discovery_client = DiscoveryClient(
                anonymous_client, base_url=repertoire_url
            )
        self.discovery_client = discovery_client
        self.serviceinfo = ServiceInfo()

    async def _ensure_config(self) -> None:
        if self._config is None:
            self._logger.info("Creating Config generator for Client config")
            self._generator = ConfigGenerator()
            # Populate config settings
            self._config = self._generator.generate_config()
            await self._generator.update_statusbar()

    async def get_config(self) -> RSPConfig:
        """Retrieve RSP Config.

        Returns
        -------
        RSPConfig
            Configuration for this RSP instance.
        """
        await self._ensure_config()
        if self._config is None:
            raise ConfigError("Cannot determine config")
        return self._config

    async def ensure_authed_client(self) -> None:
        """If we do not have an authenticated client, create one."""
        if self.authed_client is None:
            auth = f"Bearer {await self._get_access_token()}"
            self.authed_client = AsyncClient(
                headers={
                    "Content-Type": "application/json",
                    "Authorization": auth,
                },
            )

    async def _get_access_token(self) -> str:
        """Get our access token, preferred methods first."""
        # We want this to be a constant static path, but...
        path = Path("/etc/nublado/secrets/token")
        if path.exists():
            return path.read_text().strip()
        # ... it's not clear when that will happen, so meanwhile...
        runtime_dir = ""
        await self._ensure_config()
        if self._config:
            # ... the config should have it...
            runtime_dir = self._config.runtime_mounts_dir
        if not runtime_dir:
            # ... or NUBLADO_RUNTIME_MOUNTS_DIR should be set...
            runtime_dir = os.environ.get("NUBLADO_RUNTIME_MOUNTS_DIR", "")
        if not runtime_dir:
            # ... or we just have to give up.
            raise TokenNotAvailableError("No access token available")
        path = Path(runtime_dir) / "secrets" / "token"
        with suppress(FileNotFoundError):
            return path.read_text().strip()
        raise TokenNotAvailableError("No access token available")

    async def get_datasets(self) -> list[str]:
        """Get datasets present in the RSP instance.

        Returns
        -------
        list[str]
           Datasets present in the RSP instance.
        """
        datasets = await self.discovery_client.datasets()
        self._logger.debug(f"Found datasets {datasets}")
        return datasets

    async def retrieve_tap_endpoints(self) -> None:
        """Retrieve TAP endpoints in this RSP instance."""
        datasets = await self.get_datasets()
        for dataset in datasets:
            self._logger.debug(f"Finding TAP endpoint for dataset {dataset}")
            url = await self.get_tap_endpoint_for_dataset(dataset)
            if url:
                self.serviceinfo.datasets[dataset] = url
                self._logger.debug(f"TAP URL for {dataset} is {url}")
            else:
                self._logger.warning(f"No TAP URL found for dataset {dataset}")
                if dataset in self.serviceinfo.datasets:
                    del self.serviceinfo.datasets[dataset]

    async def get_tap_endpoint_for_dataset(self, dataset: str) -> str | None:
        """Return the endpoint for a given dataset.

        Parameters
        ----------
        dataset
            Name of dataset.

        Returns
        -------
            URL of HTTP endpoint for TAP access to the dataset.
        """
        if retval := self.serviceinfo.datasets.get(dataset):
            self._logger.debug(
                f"Returning cached TAP URL for {dataset}: {retval}"
            )
            return retval
        # Request dataset TAP endpoint, return None if still not found.
        url = await self.discovery_client.url_for_data("tap", dataset)
        if url:
            self.serviceinfo.datasets[dataset] = url
            self._logger.info(f"Adding {dataset} url {url}")
        return url

    async def resolve_jobref_id(self, jobref_id: str) -> JobRef:
        """Return a resolved JobRef with dataset, ID, and endpoint for a
        jobref_id string.

        Parameters
        ----------
        jobref_id
            Jobref ID as known to a TAP server.

        Returns
        -------
        JobRef
            dataset, ID, and endpoint for that jobref ID.

        Raises
        ------
        UnknownDatasetError
            Raised if this jobref ID cannot be found in any dataset, or if
        there is no endpoint for the discovered dataset.

        Notes
        -----
            If the jobref ID is in the canonical form `dataset:id`
        then we trust that the jobref exists in that dataset. If there
        is no colon, then we iterate through the dataset endpoints
        looking for a query with the jobref ID. In the event that a
        given jobref ID exists for two endpoints, the first one
        encountered will be returned. The likely cause of this is two
        datasets that share an endpoint (e.g. dp02 and dp1); the odds
        of an actual jobref ID collision are very low.
        """
        self._logger.debug(f"Resolving jobref_id {jobref_id}")
        if jobref_id.find(":") > -1:
            dataset, new_j_id = jobref_id.split(":", 1)
            endpoint = await self.get_tap_endpoint_for_dataset(dataset)
            if endpoint is None:
                msg = f"Cannot find TAP URL for dataset {dataset}"
                self._logger.warning(msg)
                raise UnknownDatasetError(msg)
            return JobRef(
                dataset=dataset, jobref_id=new_j_id, endpoint=endpoint
            )
        await self.ensure_authed_client()
        await self.retrieve_tap_endpoints()
        for dataset, endpoint in self.serviceinfo.datasets.items():
            url = f"{endpoint}/async/{jobref_id}"
            if self.authed_client is None:
                raise ClientError("No authenticated client")
            resp = await self.authed_client.get(url)
            if resp.status_code == 200:
                return JobRef(
                    dataset=dataset, jobref_id=jobref_id, endpoint=endpoint
                )
            if resp.status_code != 404:
                self._logger.warning(
                    f"Unexpected status code {resp.status_code} from {url}"
                )
        raise UnknownDatasetError(f"No dataset for jobref ID {jobref_id}")

    async def get_query_history(
        self, limit: int = 5
    ) -> dict[str, list[dict[str, str]]]:
        """Return a dict of endpoint-to-last-limit query IDs.

        Parameters
        ----------
        limit
            How many results to return.  Set to zero or negative for all
            queries.

        Returns
        -------
        dict[str, list[dict[str, str]]]
            Outer key of the dict is the dataset name; each item of the list
        is a jobref, which is a string-to-string mapping.
        """
        retval: dict[str, list[dict[str, str]]] = {}
        params = {"last": str(limit)} if limit and limit > 0 else {}
        await self.ensure_authed_client()
        await self.retrieve_tap_endpoints()
        epoch = "1970-01-01T00:00:00.000Z"
        if self.authed_client is None:
            raise ClientError("No authenticated client")
        for dataset, ep in self.serviceinfo.datasets.items():
            resp = await self.authed_client.get(ep + "/async", params=params)
            if resp.status_code >= 300:
                msg = f"Status {resp.status_code} from {ep}/async; skipping"
                self._logger.warning(msg)
                continue
            # This could be done with pyvo, but then you have to deal with
            # astropy.Time, and since the textual representation of times
            # sort lexically just fine, it ends up being more trouble than
            # using xmltodict.
            history = xmltodict.parse(resp.text, force_list=("uws:jobref",))
            if jobrefs := history.get("uws:jobs", {}).get("uws:jobref"):
                # Sort jobrefs by timestamp
                jobrefs.sort(
                    key=lambda e: e.get("uws:creationTime", epoch),
                    reverse=True,
                )
                self._logger.debug(f"{dataset} jobs -> {jobrefs}")
                retval[dataset] = jobrefs
        return retval

    async def get_environment_name(self) -> str | None:
        """Get the environment name of this RSP instance.

        Returns
        -------
        str|None
            Name of the environment, or ``None`` if unknown.

        Notes
        -----
        What we get here isn't a URL we can use.  We use this in the statusbar
        to report which RSP instance this is.  It might look like a URL, but
        it shouldn't be treated as an endpoint; that's what the landing page
        URL is for.
        """
        if not self.serviceinfo.environment_name:
            nm = await self.discovery_client.environment_name()
            if not nm:
                return None
            self.serviceinfo.environment_name = nm
        return self.serviceinfo.environment_name

    async def _get_ui_url(self, func: str) -> str | None:
        """Get an internal service URL.

        Parameters
        ----------
        func
            UI endpoint name, describing its function.

        Returns
        -------
        str|None
            URL for that UI endpoint, or ``None`` if not found.
        """
        if func not in self.serviceinfo.ui:
            url = await self.discovery_client.url_for_ui(func)
            self._logger.debug(f"UI endpoint for {func} is {url}")
            if not url:
                return None
            self.serviceinfo.ui[func] = url
        return self.serviceinfo.ui[func]

    async def get_logout_url(self) -> str | None:
        """Get the URL used to log out of this RSP instance.

        Returns
        -------
        str|None
            URL used for logout or ``None`` if not found.
        """
        return await self._get_ui_url("logout")

    async def get_squareone_url(self) -> str | None:
        """Get the URL for the landing page of this RSP instance.

        Returns
        -------
        str|None
            URL used for landing page or ``None`` if unknown.

        Notes
        -----
        The actual service for the landing page is called "squareone",
        not "landing_page"; however the function of the squareone service
        is indeed to provide a landing page for an RSP instance.
        """
        return await self._get_ui_url("squareone")

    async def _get_svc_url(self, svc: str) -> str | None:
        """Get an internal service URL.

        Parameters
        ----------
        svc
            Service name

        Returns
        -------
        str|None
            URL for that service, or ``None`` if not found.
        """
        if svc not in self.serviceinfo.service:
            url = await self.discovery_client.url_for_internal(svc)
            self._logger.debug(f"Service endpoint for {svc} is {url}")
            if not url:
                return None
            self.serviceinfo.service[svc] = url
        return self.serviceinfo.service[svc]

    async def get_times_square_url(self) -> str | None:
        """Get the URL used for Times Square in this RSP instance.

        Returns
        -------
        str|None
            URL used for the Times Square service or ``None`` if unknown.
        """
        return await self._get_svc_url("times-square")

    async def get_serviceinfo(self) -> ServiceInfo:
        """Return a structure with all the service info we care about.  Prime
        the cache by asking for everything, and then hand back the whole
        structure.

        Returns
        -------
        ServiceInfo
            A fully-populated set of service information.
        """
        async with asyncio.TaskGroup() as tg:
            tasks = (
                self.get_times_square_url,
                self.get_logout_url,
                self.get_squareone_url,
                self.retrieve_tap_endpoints,
                self.get_environment_name,
            )
            [tg.create_task(task()) for task in tasks]
        return self.serviceinfo
