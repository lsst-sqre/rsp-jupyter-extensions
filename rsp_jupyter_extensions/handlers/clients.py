"""Discovery and TAP clients used by the query extension and others.

Used to encapsulate the queries we need to make to other RSP services.
"""

import logging

import xmltodict
from httpx import AsyncClient
from rubin.repertoire import DiscoveryClient

from ._utils import _get_access_token


class RSPClient:
    """Convenience class to make accessing RSP services easy.

    It includes a discovery client for finding services and datasets,
    an anonymous client for use where we don't need to send a token
    (such as discovery), and an authenticated client for those cases where
    we do need to send a token (such as TAP or Times Square).

    It also includes convenience methods for finding commonly-used endpoints.

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
        if authed_client is None:
            authed_client = AsyncClient(
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {_get_access_token()}",
                },
            )
        self.authed_client = authed_client
        if discovery_client is None:
            discovery_client = DiscoveryClient(
                anonymous_client, base_url=repertoire_url
            )
        self.discovery_client = discovery_client
        self.dataset_urls: dict[str, str] = {}

    async def get_datasets(self) -> list[str]:
        datasets = await self.discovery_client.datasets()
        self._logger.debug(f"Found datasets {datasets}")
        return datasets

    async def get_tap_endpoints(self) -> dict[str, str]:
        retval: dict[str, str] = {}
        datasets = await self.get_datasets()
        for dataset in datasets:
            self._logger.debug(f"Finding TAP endpoint for dataset {dataset}")
            url = await self.discovery_client.url_for_data("tap", dataset)
            if url:
                retval[dataset] = url
                self.dataset_urls[dataset] = url
                self._logger.debug(f"TAP URL for {dataset} is {url}")
            else:
                self._logger.warning(f"No TAP URL found for dataset {dataset}")
        return retval

    async def get_tap_endpoint_for_dataset(self, dataset: str) -> str | None:
        if retval := self.dataset_urls.get(dataset):
            self._logger.debug(
                f"Returning cached TAP URL for {dataset}: {retval}"
            )
            return retval
        # Rescan datasets, return None if still not found.
        return (await self.get_tap_endpoints()).get(dataset)

    async def get_query_history(
        self, limit: int = 5
    ) -> dict[str, list[dict[str, str]]]:
        """Return a dict of endpoint-to-last-limit query IDs.

        Set limit to zero or negative to get all queries.
        """
        retval: dict[str, list[dict[str, str]]] = {}
        params = {"last": str(limit)} if limit and limit > 0 else {}
        endpoints = await self.get_tap_endpoints()
        epoch = "1970-01-01T00:00:00.000Z"
        for dataset, ep in endpoints.items():
            resp = await self.authed_client.get(ep + "/async", params=params)
            if resp.status_code >= 300:
                msg = f"Status {resp.status_code} from {ep}/async; skipping"
                self._logger.warning(msg)
                continue
            history = xmltodict.parse(resp.text, force_list=("uws:jobref",))
            if jobrefs := history.get("uws:jobs", {}).get("uws:jobref"):
                # Sort jobrefs by timestamp
                jobrefs.sort(
                    key=lambda e: (e.get("uws:creationTime"), epoch),
                    reverse=True,
                )
                self._logger.debug(f"{dataset} jobs -> {jobrefs}")
                retval[dataset] = jobrefs
        return retval

    async def get_environment_name(self) -> str | None:
        """Note that what we get here isn't a URL we can use.  We use this
        in the statusbar to report which RSP instance this is.
        """
        # I tried await self.discovery_client.environment_name() ...
        # error: "DiscoveryClient" has no attribute "environment_name"
        return await self.get_landing_page_url()

    async def get_logout_url(self) -> str | None:
        url = await self.discovery_client.url_for_ui("logout")
        self._logger.debug(f"Logout URL is {url}")
        return url

    async def get_landing_page_url(self) -> str | None:
        url = await self.discovery_client.url_for_ui("squareone")
        self._logger.debug(f"Landing page URL is {url}")
        return url

    async def get_times_square_url(self) -> str | None:
        url = await self.discovery_client.url_for_internal("times-square")
        self._logger.debug(f"Times Square URL is {url}")
        return url
