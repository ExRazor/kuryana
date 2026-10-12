import asyncio
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Type, TypeVar, Union
from urllib.parse import urljoin

import primp
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from app import MYDRAMALIST_WEBSITE

T = TypeVar("T", bound="Parser")


ScrapeTypes = {
    "search": urljoin(MYDRAMALIST_WEBSITE, "search?q="),
    "page": MYDRAMALIST_WEBSITE,
}

# rotate browser fingerprints; firefox/safari pass Cloudflare far more reliably
# than the Chromium TLS fingerprint from datacenter IPs
IMPERSONATE_PROFILES = ("firefox", "safari", "chrome")
REQUEST_TIMEOUT = 10  # seconds
RETRY_STATUSES = frozenset({403, 429, 503})

_clients: Dict[str, primp.Client] = {}
_clients_lock = threading.Lock()


def _client_for(profile: str) -> primp.Client:
    """Shared client per profile so cf_bm cookies survive across requests."""
    with _clients_lock:
        client = _clients.get(profile)
        if client is None:
            client = primp.Client(
                impersonate=profile,
                timeout=REQUEST_TIMEOUT,
                proxy=os.environ.get("SCRAPER_PROXY") or None,
            )
            _clients[profile] = client
        return client


def _is_challenge(resp: primp.Response) -> bool:
    if resp.status_code in RETRY_STATUSES:
        return True
    return str(resp.headers.get("cf-mitigated") or "").lower() == "challenge"


class Parser:
    """Main Parser"""

    headers: Dict[str, str] = {
        "Referer": MYDRAMALIST_WEBSITE,
    }

    def __init__(
        self, soup: BeautifulSoup | None, query: str, code: int, ok: bool
    ) -> None:
        self.soup = soup
        self.query = query
        self.status_code = code
        self.ok = ok

    @classmethod
    async def scrape(cls: Type[T], query: str, t: str) -> T:
        if t not in ScrapeTypes.keys():
            raise Exception("Invalid type")

        # parse url
        url = urljoin(ScrapeTypes[t], query)
        if t == "search":
            url = ScrapeTypes[t] + query

        ok = False
        code = 500  # default to 500, internal server error
        soup = None

        for profile in IMPERSONATE_PROFILES:
            try:
                # primp is sync; keep the event loop free while it blocks
                resp = await asyncio.to_thread(
                    _client_for(profile).get, url, headers=Parser.headers
                )
            except Exception:
                continue  # timeout/connect error -> try the next profile

            code = resp.status_code
            ok = resp.status_code == 200

            if _is_challenge(resp):
                continue  # Cloudflare block -> rotate fingerprint

            # set the main soup var
            soup = BeautifulSoup(
                resp.text,
                "html.parser",
            )
            break

        return cls(soup, query, code, ok)

    # get page err, if possible
    def res_get_err(self) -> Dict[str, Any]:
        if self.soup is None:
            return {}

        container = self.soup.find("div", class_="app-body")

        # if the page was not found,
        # or there was a problem with scraping,
        # try to get the error and return the err message
        err: Dict[str, Any] = {}

        if container is None:
            return err

        try:
            err["code"] = self.status_code
            err["error"] = True
            err["description"] = {
                "title": container.find("div", class_="box-body")
                .find("h1")
                .get_text()
                .strip(),
                "info": container.find("div", class_="box-body")
                .find("p")
                .get_text()
                .strip(),
            }

        except Exception:
            pass

        return err


class BaseSearch(Parser):
    def __init__(self, soup: BeautifulSoup, query: str, code: int, ok: bool) -> None:
        super().__init__(soup, query, code, ok)

        self.search_results: Dict[str, List] = {}  # search

    def search(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "results": self.search_results,
            "scrape_date": datetime.now(timezone.utc),
        }


class BaseFetch(Parser):
    def __init__(self, soup: BeautifulSoup, query: str, code: int, ok: bool) -> None:
        super().__init__(soup, query, code, ok)

        self.info: Dict[str, Any] = {
            "link": urljoin(MYDRAMALIST_WEBSITE, query)  # add `link` first data
        }  # fetch

        self._img_attrs = ["src", "data-cfsrc", "data-src"]

    def fetch(self) -> Dict[str, Any]:
        return {
            "slug_query": self.query,
            "data": self.info,
            "scrape_date": datetime.now(timezone.utc),
        }

    def _get(self) -> None:
        """handler for parser, override in subclass"""

    def _get_poster(self, container: Union[Tag, NavigableString]) -> Union[str, Any]:
        poster = container.find("img")

        if poster is None:
            return ""

        for i in self._img_attrs:
            if poster.has_attr(i):  # type: ignore
                return poster[i]  # type: ignore

        # blank if none
        return ""

    # get the drama details <= statistics section is added in here
    def _get_details(self, classname: str) -> None:
        if self.soup is None:
            return

        details = self.soup.find("ul", class_=classname)  # "list m-a-0 hidden-md-up"
        if details is None:
            return

        try:
            self.info["details"] = {}
            all_details = details.find_all("li")

            for i in all_details:
                # get each li from <ul>
                _title = i.find("b").text.strip()

                # append each to sub object
                self.info["details"][
                    _title.replace(":", "").replace(" ", "_").lower()
                ] = i.text.replace(
                    _title + " ", ""
                ).strip()  # remove leading and trailing white spaces

        except Exception:
            # do nothing, if there was a problem
            pass

    # rating handler, (since it could be N/A which is not convertable to float)
    def _handle_rating(
        self, component: Union[Tag, NavigableString]
    ) -> Union[str, float, Any]:
        try:
            return float(component.text)
        except Exception:
            pass

        return component.text
