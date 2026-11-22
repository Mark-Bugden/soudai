"""rozhodnuti.justice.cz's open data: the index of published decisions by year, month and day, and the
day pages that list them, 100 to a page.

Each decision names its judge (`autor`). Nothing here drops it, because the raw cache keeps responses
as they came, but the parse step in milestone 3 does, so no derived table holds judges' names. Full
texts (`odkaz`) are never fetched.
"""

import re
from datetime import date

from .http import UnexpectedResponse

API = "https://rozhodnuti.justice.cz/api/opendata"
PAGE_SIZE = 100

# A case number: senate, register, number/year, and -document within the case. Every one of the
# 2,849 case numbers in the feasibility check's six days matched.
CASE_NUMBER = re.compile(r"^(\d+)\s+([A-Za-z]+)\s+(\d+)/(\d{4})(?:-(\d+))?$")


def parse_case_number(text):
    """(senate, register, number, year, document) from e.g. "15 C 384/2022-15"; document may be None.
    Returns None if the text isn't a case number."""
    match = CASE_NUMBER.match(text.strip())
    if match is None:
        return None
    senate, register, number, year, document = match.groups()
    return int(senate), register, int(number), int(year), None if document is None else int(document)


def years(client, refresh=False):
    """{year: decisions published that year}."""
    return {int(row["rok"]): row["pocet"] for row in _list(client.get(API, refresh=refresh), "rok", "pocet")}


def months(client, year, refresh=False):
    """{month: decisions published that month}."""
    response = client.get(f"{API}/{year}", refresh=refresh)
    return {int(row["mesic"]): row["pocet"] for row in _list(response, "mesic", "pocet")}


def days(client, year, month, refresh=False):
    """{date: decisions published that day}, for the days that have any."""
    response = client.get(f"{API}/{year}/{month}", refresh=refresh)
    return {date.fromisoformat(row["datum"]): row["pocet"] for row in _list(response, "datum", "pocet")}


def day_page(client, day, page, refresh=False):
    """One page of a day's decisions: {"items": [...], "totalPages": ..., "totalElements": ..., ...}."""
    response = client.get(f"{API}/{day.year}/{day.month}/{day.day}", params={"page": page}, refresh=refresh)
    data = _json(response)
    if not isinstance(data, dict) or not {"items", "totalPages", "totalElements"} <= set(data):
        raise UnexpectedResponse(f"not a day page: {response.text[:200]}")
    return data


def day_decisions(client, day, refresh=False):
    """Every decision published on a day, page by page from page 0."""
    first = day_page(client, day, 0, refresh=refresh)
    yield from first["items"]
    for page in range(1, first["totalPages"]):
        yield from day_page(client, day, page, refresh=refresh)["items"]


def pages(count):
    """How many pages a day with `count` decisions has."""
    return -(-count // PAGE_SIZE)


def _list(response, *keys):
    rows = _json(response)
    if not isinstance(rows, list) or not all(set(keys) <= set(row) for row in rows):
        raise UnexpectedResponse(f"not an index of {keys}: {response.text[:200]}")
    return rows


def _json(response):
    if response.status != 200 or not (response.content_type or "").startswith("application/json"):
        raise UnexpectedResponse(f"HTTP {response.status} ({response.content_type}) from {response.url}")
    return response.json()
