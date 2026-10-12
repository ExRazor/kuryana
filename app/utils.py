from typing import Any, Dict, Tuple

from app.handlers.fetch import (
    FetchCast,
    FetchDrama,
    FetchDramaList,
    FetchEpisodes,
    FetchList,
    FetchPerson,
    FetchReviews,
)
from app.handlers.parser import RETRY_STATUSES, Parser
from app.handlers.search import Search
from app.handlers.seasonal import parse_seasonal


def error(code: int, description: str) -> Dict[str, Any]:
    return {
        "error": True,
        "code": code,
        "description": (
            "404 Not Found" if code == 404 else description
        ),  # prioritize error 404
    }


# search function
async def search_func(query: str) -> Tuple[int, Dict[str, Any]]:
    f = await Search.scrape(query=query, t="search")
    if not f.ok:
        return f.status_code, error(f.status_code, "An unexpected error occurred.")
    else:
        try:
            f._get_search_results()
        except Exception:
            return 502, error(502, "Failed to parse MyDramaList page.")

    return f.status_code, f.search()


fs = {
    "drama": FetchDrama,
    "person": FetchPerson,
    "cast": FetchCast,
    "reviews": FetchReviews,
    "lists": FetchList,
    "dramalist": FetchDramaList,
    "episodes": FetchEpisodes,
}


# fetch function
async def fetch_func(query: str, t: str) -> Tuple[int, Dict[str, Any]]:
    if t not in fs.keys():
        raise Exception("Invalid Error")

    f = await fs[t].scrape(query=query, t="page")
    if not f.ok:
        err = f.res_get_err()
        if not err:
            # no parsable MDL error page: Cloudflare block or upstream failure
            if f.status_code in RETRY_STATUSES:
                return f.status_code, error(
                    f.status_code, "Blocked by Cloudflare. Try again later."
                )
            return f.status_code, error(f.status_code, "Upstream error.")
        return f.status_code, err

    try:
        f._get()
    except Exception:
        return 502, error(502, "Failed to parse MyDramaList page.")

    return f.status_code, f.fetch()


# seasonal function
async def seasonal_func(year: int, quarter: int) -> Tuple[int, Dict[str, Any]]:
    f = await Parser.scrape(query=f"episode-calendar/q{quarter}-{year}", t="page")
    if not f.ok or f.soup is None:
        return f.status_code, error(f.status_code, "An unexpected error occurred.")

    return f.status_code, {
        "year": year,
        "quarter": quarter,
        "data": parse_seasonal(f.soup),
    }
