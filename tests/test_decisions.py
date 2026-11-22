"""The published-decisions stage: listing, staleness, parsing and the table it writes. Offline."""

import json
from datetime import date

import pyarrow.parquet
import pytest
from conftest import FIXTURES, FakeClient, make_response

from soudai import decisions, reference, rozhodnuti
from soudai.http import request_key

API = rozhodnuti.API


@pytest.fixture(scope="module")
def page():
    """The saved first page of 2023-03-15, made into a whole day of 100 decisions."""
    record = json.loads((FIXTURES / "rozhodnuti" / "day_2023_03_15_page_0.json").read_text(encoding="utf-8"))
    return record["response"] | {"totalPages": 1, "totalElements": 100}


@pytest.fixture(scope="module")
def names():
    courts = reference.courts()
    return {name: court["code"] for court in courts for name in court["rozhodnuti_names"].split("; ")}


def index(key, values):
    return [{key: value, "pocet": 1} for value in values]


def test_a_row_keeps_only_what_the_plan_names(page, names):
    item = page["items"][0]
    assert set(item) >= {"autor", "klicovaSlova", "zminenaUstanoveni", "odkaz", "ecli"}
    assert decisions.row(item, names) == {
        "court": "OSVYCNA",
        "court_name": "Okresní soud v Náchodě",
        "case_number": "15 C 384/2022-15",
        "senate": 15,
        "register": "C",
        "number": 384,
        "year": 2022,
        "document": 15,
        "decision_date": date(2023, 1, 30),
        "publication_date": date(2023, 3, 15),
        "subject": "O zaplacení 25 455 Kč s příslušenstvím",  # as given, with no-break spaces
    }
    assert list(decisions.row(item, names)) == decisions.SCHEMA.names


def test_a_case_number_that_doesnt_parse_keeps_its_text(names):
    row = decisions.row(
        {"jednaciCislo": "Nc 12/2022", "soud": "Krajský soud v Brně", "datumVydani": "x"}, names
    )
    assert (row["case_number"], row["senate"], row["number"], row["court"]) == (
        "Nc 12/2022",
        None,
        None,
        None,
    )
    assert row["decision_date"] is None


@pytest.mark.parametrize(
    "court_name, court, level",
    [
        ("Okresní soud v Náchodě", "OSVYCNA", "district"),
        ("Krajský soud v Hradci Králové, pobočka Pardubice", None, "regional"),
        ("Městský soud v Praze", None, "regional"),
        ("Vrchní soud v Praze", None, "high"),
        ("Nejvyšší soud", None, "supreme"),
        ("(nezadán)", None, "not given"),
        ("Soud v Kocourkově", None, "other"),
    ],
)
def test_court_levels(court_name, court, level):
    assert decisions.level(court_name, court) == level


def test_a_listing_is_stale_if_fetched_before_its_period_ended():
    client = FakeClient()
    url = f"{API}/2026/11"
    assert not decisions.stale(client, url, date(2026, 11, 30))  # not cached at all
    client.fetched_at[request_key("GET", url)] = "2026-11-22T09:00:00+00:00"
    assert decisions.stale(client, url, date(2026, 11, 30))
    assert decisions.stale(client, url, date(2026, 11, 22))  # fetched on the period's last day
    assert not decisions.stale(client, url, date(2026, 11, 21))


def test_the_listing_runs_from_2020_to_the_snapshot_and_refreshes_what_was_incomplete():
    responses = {
        API: index("rok", [2019, 2020, 2021]),
        f"{API}/2020": index("mesic", [11, 12]),
        f"{API}/2021": index("mesic", [1, 2]),
        f"{API}/2020/11": index("datum", ["2020-11-30"]),
        f"{API}/2020/12": index("datum", ["2020-12-01", "2020-12-31"]),
        f"{API}/2021/1": index("datum", ["2021-01-04", "2021-01-20"]),
    }
    client = FakeClient(
        [(("GET", url, None), make_response(url, 200, data)) for url, data in responses.items()]
    )
    client.fetched_at[request_key("GET", f"{API}/2021/1")] = "2021-01-15T12:00:00+00:00"  # mid-month
    client.fetched_at[request_key("GET", f"{API}/2020/12")] = "2021-01-02T12:00:00+00:00"  # after it ended
    days = decisions.listing(client, date(2021, 1, 10))
    assert days == [
        (date(2020, 11, 30), 1),
        (date(2020, 12, 1), 1),
        (date(2020, 12, 31), 1),
        (date(2021, 1, 4), 1),
    ]
    refreshed = {url: refresh for _, url, _, refresh in client.requests}
    assert refreshed[API] is True  # the year index is always fetched afresh
    assert refreshed[f"{API}/2021/1"] is True
    assert refreshed[f"{API}/2020/12"] is False
    assert f"{API}/2021/2" not in refreshed and f"{API}/2019" not in refreshed


def test_a_days_items_come_from_every_page_page_0_names():
    day, url = date(2026, 1, 5), f"{API}/2026/1/5?page="
    pages = [{"items": [{"n": n}], "totalPages": 3, "totalElements": 3} for n in range(3)]
    client = FakeClient([(("GET", url + str(n), None), make_response(url, 200, pages[n])) for n in range(3)])
    assert decisions.day_items(client, day) == (3, [{"n": 0}, {"n": 1}, {"n": 2}])


@pytest.fixture
def parsed_day(page):
    url = f"{API}/2023/3/15?page=0"
    client = FakeClient([(("GET", url, None), make_response(url, 200, page))])
    return decisions.parse(client, [(date(2023, 3, 15), 100)], reference.courts())


def test_parsing_a_day_drops_the_judges(parsed_day):
    columns, judges, disagreements = parsed_day
    assert list(columns) == decisions.SCHEMA.names
    assert len(columns["case_number"]) == 100
    assert judges == {"REDACTED"}
    assert disagreements == []


def test_a_day_whose_counts_disagree_is_reported(page):
    url = f"{API}/2023/3/15?page=0"
    client = FakeClient([(("GET", url, None), make_response(url, 200, page))])
    _, _, disagreements = decisions.parse(client, [(date(2023, 3, 15), 101)], reference.courts())
    assert disagreements == [(date(2023, 3, 15), 101, 100, 100)]


def test_the_table_round_trips_with_its_snapshot_and_no_judges(tmp_path, parsed_day):
    columns, _, disagreements = parsed_day
    path = tmp_path / "decisions.parquet"
    decisions.write(columns, date(2023, 3, 15), path)
    table = pyarrow.parquet.read_table(path)
    assert table.schema.names == decisions.SCHEMA.names
    assert "autor" not in table.schema.names
    assert table.schema.metadata[b"snapshot"] == b"2023-03-15"
    assert table.num_rows == 100
    rows = table.to_pylist()
    assert {row["court"] for row in rows if row["court_name"] == "Okresní soud v Náchodě"} == {"OSVYCNA"}
    assert {row["court"] for row in rows if row["court_name"].startswith("Krajský")} == {None}
    lines = decisions.summary(columns, disagreements, [], path)
    assert lines[0].startswith("100 decisions published from 2020")
    assert "District-like court names that don't map to a court: none" in lines


@pytest.mark.parametrize(
    "autor, name",
    [
        ("JUDr. Jan Novák, Ph.D.", "Jan Novák"),
        ("JUDr. et Mgr. Eva Malá", "Eva Malá"),
        ("Mgr. Petr Svoboda, LL.M.", "Petr Svoboda"),
        ("Ing. Bc. Jana Dvořáková, MBA", "Jana Dvořáková"),
    ],
)
def test_judges_names_lose_their_titles(autor, name):
    assert decisions.bare_name(autor) == name


def test_a_judges_name_in_a_subject_is_caught():
    columns = {"court_name": ["Okresní soud v Náchodě"], "subject": ["o zaplacení, žalobce Jan Novák"]}
    assert decisions.judges_in(columns, {"JUDr. Jan Novák", "Mgr. Eva Malá"}) == ["Jan Novák"]
    assert decisions.judges_in(columns, {"Mgr. Eva Malá"}) == []
