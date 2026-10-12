"""Retry/rotation logic in Parser.scrape, tested without any network access."""

import asyncio

from app.handlers import parser
from app.handlers.parser import Parser


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        headers: dict | None = None,
        text: str = "<html><body></body></html>",
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text


class FakeClient:
    """Records calls; raises or returns per scripted outcomes."""

    def __init__(self, outcomes: list) -> None:
        self.outcomes = outcomes
        self.calls = 0

    def get(self, url: str, headers: dict | None = None) -> FakeResponse:
        outcome = self.outcomes[min(self.calls, len(self.outcomes) - 1)]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def with_fakes(monkeypatch, firefox, safari=None, chrome=None) -> dict:
    clients = {
        "firefox": firefox,
        "safari": safari or FakeClient([]),
        "chrome": chrome or FakeClient([]),
    }
    monkeypatch.setattr(parser, "_clients", clients)
    return clients


def run(query: str = "18452-goblin") -> Parser:
    return asyncio.run(Parser.scrape(query=query, t="page"))


def test_first_profile_ok_no_rotation(monkeypatch):
    ff = FakeClient([FakeResponse(200)])
    clients = with_fakes(monkeypatch, ff)

    p = run()

    assert p.ok
    assert p.status_code == 200
    assert p.soup is not None
    assert clients["firefox"].calls == 1
    assert clients["safari"].calls == 0
    assert clients["chrome"].calls == 0


def test_rotates_on_403_challenge(monkeypatch):
    ff = FakeClient([FakeResponse(403, headers={"cf-mitigated": "challenge"})])
    sf = FakeClient([FakeResponse(200)])
    clients = with_fakes(monkeypatch, ff, sf)

    p = run()

    assert p.ok
    assert p.status_code == 200
    assert clients["firefox"].calls == 1
    assert clients["safari"].calls == 1
    assert clients["chrome"].calls == 0


def test_rotates_on_cf_mitigated_even_with_200(monkeypatch):
    ff = FakeClient([FakeResponse(200, headers={"cf-mitigated": "challenge"})])
    sf = FakeClient([FakeResponse(200)])
    clients = with_fakes(monkeypatch, ff, sf)

    p = run()

    assert p.ok
    assert clients["safari"].calls == 1


def test_rotates_on_429_and_503(monkeypatch):
    for status in (429, 503):
        ff = FakeClient([FakeResponse(status)])
        sf = FakeClient([FakeResponse(status)])
        ch = FakeClient([FakeResponse(200)])
        clients = with_fakes(monkeypatch, ff, sf, ch)

        p = run()

        assert p.ok, f"expected recovery after {status}"
        assert clients["chrome"].calls == 1


def test_rotates_on_exception(monkeypatch):
    ff = FakeClient([TimeoutError("connect timed out")])
    sf = FakeClient([FakeResponse(200)])
    clients = with_fakes(monkeypatch, ff, sf)

    p = run()

    assert p.ok
    assert clients["safari"].calls == 1


def test_all_profiles_challenged(monkeypatch):
    ff = FakeClient([FakeResponse(403)])
    sf = FakeClient([FakeResponse(403)])
    ch = FakeClient([FakeResponse(403)])
    clients = with_fakes(monkeypatch, ff, sf, ch)

    p = run()

    assert not p.ok
    assert p.status_code == 403
    assert p.soup is None
    assert all(c.calls == 1 for c in clients.values())


def test_all_profiles_raise(monkeypatch):
    ff = FakeClient([TimeoutError("boom")])
    sf = FakeClient([OSError("boom")])
    ch = FakeClient([TimeoutError("boom")])
    with_fakes(monkeypatch, ff, sf, ch)

    p = run()

    assert not p.ok
    assert p.status_code == 500  # never got a response
    assert p.soup is None


def test_no_retry_on_404(monkeypatch):
    ff = FakeClient(
        [FakeResponse(404, text="<html><div class='app-body'></div></html>")]
    )
    clients = with_fakes(monkeypatch, ff)

    p = run()

    assert not p.ok
    assert p.status_code == 404
    assert p.soup is not None  # 404 page is still parsed for the MDL error body
    assert clients["safari"].calls == 0
