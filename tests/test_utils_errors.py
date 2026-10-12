"""Error handling in app/utils.py, tested without any network access."""

import asyncio

from app import utils
from app.handlers.parser import Parser
from app.utils import fetch_func, search_func


class FakeScraper(Parser):
    """Prebuilt result that skips the network entirely."""

    def __init__(self, result, parse_raises=None):  # type: ignore[no-untyped-def]
        super().__init__(result.get("soup"), "query", result["code"], result["ok"])
        self.result = result
        self.parse_raises = parse_raises
        self.parsed = False

    @classmethod
    async def scrape(cls, query: str, t: str) -> "FakeScraper":
        return cls._instance

    def _get(self) -> None:
        self.parsed = True
        if self.parse_raises:
            raise self.parse_raises

    def _get_search_results(self) -> None:
        self._get()

    def fetch(self):  # type: ignore[no-untyped-def]
        return {"slug_query": self.query, "data": {}, "scrape_date": None}

    def search(self):  # type: ignore[no-untyped-def]
        return {"query": self.query, "results": {}, "scrape_date": None}


def install(monkeypatch, scraper) -> None:
    FakeScraper._instance = scraper
    monkeypatch.setitem(utils.fs, "drama", FakeScraper)
    monkeypatch.setattr(utils.Search, "scrape", classmethod(lambda cls, **kw: _async(scraper)))


async def _async(scraper):  # type: ignore[no-untyped-def]
    return scraper


def blocked_result(code: int = 403) -> dict:
    return {"ok": False, "code": code, "soup": None}


def test_403_without_error_page_reports_cloudflare(monkeypatch):
    install(monkeypatch, FakeScraper(blocked_result(403)))

    code, body = asyncio.run(fetch_func("18452-goblin", "drama"))

    assert code == 403
    assert body == {
        "error": True,
        "code": 403,
        "description": "Blocked by Cloudflare. Try again later.",
    }


def test_429_reports_cloudflare(monkeypatch):
    install(monkeypatch, FakeScraper(blocked_result(429)))

    code, body = asyncio.run(fetch_func("18452-goblin", "drama"))

    assert code == 429
    assert "Cloudflare" in body["description"]


def test_500_without_error_page_reports_upstream(monkeypatch):
    install(monkeypatch, FakeScraper(blocked_result(500)))

    code, body = asyncio.run(fetch_func("18452-goblin", "drama"))

    assert code == 500
    assert body["description"] == "Upstream error."


def test_404_error_page_still_parsed(monkeypatch):
    html = """
    <html><div class="app-body"><div class="box-body"><h1> Title </h1><p> Info </p></div></div></html>
    """
    install(monkeypatch, FakeScraper({"ok": False, "code": 404, "soup": _soup(html)}))

    code, body = asyncio.run(fetch_func("unknown-slug", "drama"))

    assert code == 404
    assert body["error"] is True
    assert body["description"]["title"] == "Title"
    assert body["description"]["info"] == "Info"


def test_parse_failure_returns_502(monkeypatch):
    scraper = FakeScraper({"ok": True, "code": 200, "soup": _soup("<html></html>")})
    scraper.parse_raises = RuntimeError("selector broke")
    install(monkeypatch, scraper)

    code, body = asyncio.run(fetch_func("18452-goblin", "drama"))

    assert code == 502
    assert body == {
        "error": True,
        "code": 502,
        "description": "Failed to parse MyDramaList page.",
    }
    assert scraper.parsed  # _get() was attempted


def test_search_parse_failure_returns_502(monkeypatch):
    scraper = FakeScraper({"ok": True, "code": 200, "soup": _soup("<html></html>")})
    scraper.parse_raises = RuntimeError("selector broke")
    install(monkeypatch, scraper)

    code, body = asyncio.run(search_func("goblin"))

    assert code == 502
    assert body["description"] == "Failed to parse MyDramaList page."


def test_ok_path_unchanged(monkeypatch):
    scraper = FakeScraper({"ok": True, "code": 200, "soup": _soup("<html></html>")})
    install(monkeypatch, scraper)

    code, body = asyncio.run(fetch_func("18452-goblin", "drama"))

    assert code == 200
    assert body["slug_query"] == "query"
    assert scraper.parsed


def _soup(html: str):  # type: ignore[no-untyped-def]
    from bs4 import BeautifulSoup

    return BeautifulSoup(html, "html.parser")
