from pathlib import Path

from bs4 import BeautifulSoup

from app.handlers.seasonal import parse_seasonal


def test_parse_seasonal() -> None:
    html = (Path(__file__).parent / "fixture" / "seasonal.html").read_text()
    items = parse_seasonal(BeautifulSoup(html, "html.parser"))

    assert len(items) == 3  # the duplicated card is dropped
    first = items[0]
    assert first["id"] == "793470"
    assert first["slug"] == "/793470-you-ta-chen-lun-hou-li-xiao-jie-sha-feng-le"
    assert first["title"] == "After Seducing Him, She Becomes Unstoppable"
    assert first["type"] == "Chinese Drama"
    assert first["rating"] == 6.8
    assert first["release_date"] == "January 1, 2025"
    assert first["genres"] == ["Thriller", "Romance", "Drama"]
    assert items[1]["rating"] is None
