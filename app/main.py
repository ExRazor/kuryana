from typing import Any, Dict

import cloudscraper  # bypassing cloudflare anti-bot
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.lib.msgspec_json import MsgSpecJSONResponse
from app.utils import fetch_func, search_func

app = FastAPI(
    title="Kuryana",
    default_response_class=MsgSpecJSONResponse,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def index() -> Dict[str, Any]:
    return {"message": "A Simple and Basic MDL Scraper API"}


@app.get("/search/q/{query}")
async def search(query: str, response: Response) -> Dict[str, Any]:
    code, r = await search_func(query=query)

    response.status_code = code
    return r


@app.get("/id/{drama_id}")
async def fetch(drama_id: str, response: Response) -> Dict[str, Any]:
    code, r = await fetch_func(query=drama_id, t="drama")

    response.status_code = code
    return r


@app.get("/id/{drama_id}/cast")
async def fetch_cast(drama_id: str, response: Response) -> Dict[str, Any]:
    code, r = await fetch_func(query=f"{drama_id}/cast", t="cast")

    response.status_code = code
    return r


@app.get("/id/{drama_id}/episodes")
async def fetch_episodes(drama_id: str, response: Response) -> Dict[str, Any]:
    code, r = await fetch_func(query=f"{drama_id}/episodes", t="episodes")

    response.status_code = code
    return r


@app.get("/id/{drama_id}/reviews")
async def fetch_reviews(
    drama_id: str, response: Response, page: int = 1
) -> Dict[str, Any]:
    code, r = await fetch_func(query=f"{drama_id}/reviews?page={page}", t="reviews")

    response.status_code = code
    return r


@app.get("/people/{person_id}")
async def person(person_id: str, response: Response) -> Dict[str, Any]:
    code, r = await fetch_func(query=f"people/{person_id}", t="person")

    response.status_code = code
    return r


@app.get("/dramalist/{user_id}")
async def dramalist(user_id: str, response: Response) -> Dict[str, Any]:
    code, r = await fetch_func(query=f"dramalist/{user_id}", t="dramalist")

    response.status_code = code
    return r


@app.get("/list/{list_id}")
async def lists(list_id: str, response: Response) -> Dict[str, Any]:
    code, r = await fetch_func(query=f"list/{list_id}", t="lists")

    response.status_code = code
    return r


# get seasonal drama list -- official api available, use it with cloudflare bypass
@app.get("/seasonal/{year}/{quarter}")
async def mdlSeasonal(year: int, quarter: int) -> Any:
    # year -> ex. ... / 2019 / 2020 / 2021 / ...
    # quarter -> every 3 months (Jan-Mar=1, Apr-Jun=2, Jul-Sep=3, Oct-Dec=4)
    # --- seasonal information --- winter --- spring --- summer --- fall ---

    scraper = cloudscraper.create_scraper()

    return scraper.post(
        "https://mydramalist.com/v1/quarter_calendar",
        data={"quarter": quarter, "year": year},
    ).json()
