"""rozhodnuti.justice.cz's open data: the index of published decisions by year, month and day, and the
day pages that list them, 100 to a page.

Each decision names its judge (`autor`). Nothing here drops it, because the raw cache keeps responses
as they came, but the parse step in milestone 3 does, so no derived table holds judges' names. Full
texts (`odkaz`) are never fetched.
"""

import re
from datetime import date

from .http import UnexpectedResponse, parsed, with_params
from .http import expect_json as _json

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
    rows = parsed(client, _index("rok"), "GET", API, refresh=refresh)
    return {int(row["rok"]): row["pocet"] for row in rows}


def months(client, year, refresh=False):
    """{month: decisions published that month}."""
    rows = parsed(client, _index("mesic"), "GET", f"{API}/{year}", refresh=refresh)
    return {int(row["mesic"]): row["pocet"] for row in rows}


def days(client, year, month, refresh=False):
    """{date: decisions published that day}, for the days that have any."""
    rows = parsed(client, _index("datum"), "GET", f"{API}/{year}/{month}", refresh=refresh)
    return {date.fromisoformat(row["datum"]): row["pocet"] for row in rows}


def day_page(client, day, page, refresh=False):
    """One page of a day's decisions: {"items": [...], "totalPages": ..., "totalElements": ..., ...}."""
    url = with_params(f"{API}/{day.year}/{day.month}/{day.day}", {"page": page})
    return parsed(client, parse_day_page, "GET", url, refresh=refresh)


def parse_day_page(response):
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


def parse_index(response, key):
    """An index: a list of rows, each with `key` (rok, mesic or datum) and `pocet`."""
    rows = _json(response)
    if not isinstance(rows, list) or not all(
        isinstance(row, dict) and {key, "pocet"} <= row.keys() for row in rows
    ):
        raise UnexpectedResponse(f"not an index by {key}: {response.text[:200]}")
    return rows


def _index(key):
    return lambda response: parse_index(response, key)
