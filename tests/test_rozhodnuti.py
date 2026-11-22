"""rozhodnuti's index and day pages, and case numbers, on saved real responses."""

import json
from datetime import date

import pytest
from conftest import FIXTURES, FakeClient, make_response

from soudai import rozhodnuti
from soudai.http import UnexpectedResponse


@pytest.fixture(scope="module")
def day_page():
    path = FIXTURES / "rozhodnuti" / "day_2023_03_15_page_0.json"
    return json.loads(path.read_text(encoding="utf-8"))["response"]


def test_the_year_index(fixture_client):
    years = rozhodnuti.years(fixture_client)
    assert years[2020] == 797 and years[2022] == 181_861
    assert sum(years.values()) == 616_458


def test_the_month_and_day_indexes(fixture_client):
    months = rozhodnuti.months(fixture_client, 2023)
    assert list(months) == list(range(1, 13)) and sum(months.values()) == 85_462
    days = rozhodnuti.days(fixture_client, 2023, 3)
    assert days[date(2023, 3, 15)] == 400
    assert date(2023, 3, 4) not in days  # days with nothing published aren't listed
    assert sum(days.values()) == months[3]


def test_a_day_page(fixture_client):
    page = rozhodnuti.day_page(fixture_client, date(2023, 3, 15), 0)
    assert (page["totalPages"], page["totalElements"], len(page["items"])) == (4, 400, 100)
    assert page["items"][0]["jednaciCislo"] == "15 C 384/2022-15"


def test_a_days_decisions_are_read_page_by_page():
    day = date(2026, 1, 5)
    url = f"{rozhodnuti.API}/2026/1/5?page="
    pages = [
        {"items": [{"n": 2 * n}, {"n": 2 * n + 1}], "totalPages": 3, "totalElements": 6} for n in range(3)
    ]
    client = FakeClient([(("GET", url + str(n), None), make_response(url, 200, pages[n])) for n in range(3)])
    assert [item["n"] for item in rozhodnuti.day_decisions(client, day)] == [0, 1, 2, 3, 4, 5]


def test_a_cached_page_that_isnt_one_is_fetched_again():
    url = f"{rozhodnuti.API}/2026/1/5?page=0"
    good = {"items": [], "totalPages": 1, "totalElements": 0}
    client = FakeClient(
        [
            (("GET", url, None), make_response(url, 200, {"error": "maintenance"}, from_cache=True)),
            (("GET", url, None), make_response(url, 200, good)),
        ]
    )
    assert rozhodnuti.day_page(client, date(2026, 1, 5), 0) == good
    assert [refresh for *_, refresh in client.requests] == [False, True]


def test_a_page_that_isnt_one_raises():
    url = f"{rozhodnuti.API}/2026/1/5?page=0"
    client = FakeClient([(("GET", url, None), make_response(url, 200, {"error": "nope"}))])
    with pytest.raises(UnexpectedResponse):
        rozhodnuti.day_page(client, date(2026, 1, 5), 0)


@pytest.mark.parametrize(
    "text, parsed",
    [
        ("15 C 384/2022-15", (15, "C", 384, 2022, 15)),
        ("17 C 291/2022", (17, "C", 291, 2022, None)),
        ("117 C 434/2022-32", (117, "C", 434, 2022, 32)),
        ("11 CO 310/2022-195", (11, "CO", 310, 2022, 195)),
        (" 4 C 91/2020-163 ", (4, "C", 91, 2020, 163)),
    ],
)
def test_case_numbers_parse(text, parsed):
    assert rozhodnuti.parse_case_number(text) == parsed


@pytest.mark.parametrize("text", ["", "C 384/2022", "15 C 384/22", "15 C 384", "15 C 384/2022-"])
def test_things_that_arent_case_numbers_dont(text):
    assert rozhodnuti.parse_case_number(text) is None


def test_every_case_number_on_a_real_page_parses(day_page):
    numbers = [item["jednaciCislo"] for item in day_page["items"]]
    assert all(rozhodnuti.parse_case_number(number) for number in numbers), numbers


def test_the_saved_page_names_no_judges(day_page):
    assert {item["autor"] for item in day_page["items"]} == {"REDACTED"}


@pytest.mark.parametrize("count, pages", [(0, 0), (1, 1), (100, 1), (101, 2), (888, 9)])
def test_pages_per_day(count, pages):
    assert rozhodnuti.pages(count) == pages
