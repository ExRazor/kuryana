from typing import Any, Dict, List

from bs4 import BeautifulSoup
from bs4.element import Tag

from app import MYDRAMALIST_WEBSITE


def _text(parent: Tag, cls: str) -> str | None:
    el = parent.find(class_=cls)
    return el.get_text(" ", strip=True) if el else None


def parse_seasonal(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """Parse the cards on /episode-calendar/q{quarter}-{year}."""
    results: Dict[str, Dict[str, Any]] = {}

    for card in soup.select("div.episode-card"):
        link = card.select_one("div.title a")
        if link is None:
            continue

        slug = str(link.get("href", "")).strip("/")
        if not slug or slug in results:
            continue

        img = card.select_one("img")
        score = _text(card, "score")
        btn = card.select_one("button[data-id]")

        results[slug] = {
            "id": btn.get("data-id") if btn else None,
            "slug": f"/{slug}",
            "link": f"{MYDRAMALIST_WEBSITE.rstrip('/')}/{slug}",
            "title": link.get_text(strip=True),
            "type": _text(card, "content-type"),
            "cover": (img.get("src") or img.get("data-src")) if img else None,
            "rating": float(score) if score else None,
            "release_date": _text(card, "release-time"),
            "synopsis": _text(card, "synopsis"),
            "genres": [g.get_text(strip=True) for g in card.select("div.genre")],
        }

    return list(results.values())
