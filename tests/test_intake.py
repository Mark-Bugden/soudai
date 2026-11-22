"""Exact intake: the docket search, the island and hole probes, and senate discovery, on fake dockets."""

import math

import pyarrow
import pyarrow.parquet
import pytest

from soudai import decisions, infosoud, intake, senates


def docket_of(n, missing=(), extra=()):
    """A fake docket: numbers 1..n, less `missing`, plus `extra`, with every question recorded."""
    asked = []

    def exists(number):
        asked.append(number)
        return (1 <= number <= n and number not in missing) or number in extra

    exists.asked = asked
    return exists


@pytest.mark.parametrize("n", [0, 1, 2, 15, 16, 17, 18, 100, 399, 400, 5_000])
@pytest.mark.parametrize("hint", [None, 1, "half", "exact", "above", "far above"])
def test_the_top_of_a_docket_is_found_whatever_the_hint(n, hint):
    hint = {"half": n // 2, "exact": n, "above": n + 7, "far above": 3 * n + 5}.get(hint, hint)
    assert intake.find_top(intake.Docket(docket_of(n)), hint) == n


def test_each_number_is_asked_once():
    exists = docket_of(400)
    docket = intake.Docket(exists)
    intake.find_top(docket, 390)
    intake.check(docket, 400, "seed")
    assert len(exists.asked) == len(set(exists.asked)) == len(docket.answers)


@pytest.mark.parametrize(
    "n, hint, most", [(400, 390, 7), (400, None, 2 * math.log2(400) + 3), (5_000, None, 28)]
)
def test_the_search_takes_few_probes(n, hint, most):
    docket = intake.Docket(docket_of(n))
    intake.find_top(docket, hint)
    assert len(docket.answers) <= most


def test_an_island_above_the_top_is_flagged():
    docket = intake.Docket(docket_of(100, extra={110}))
    top = intake.find_top(docket, 90)
    assert top == 100
    assert intake.check(docket, top, "seed") == ["island:110"]


def test_holes_below_the_top_are_flagged():
    docket = intake.Docket(docket_of(100, missing=set(range(2, 100))))
    flags = intake.check(docket, 100, "seed")
    assert len(flags) == 3 and all(flag.startswith("hole:") for flag in flags)


def test_a_clean_docket_has_no_flags_and_the_hole_probes_repeat():
    first, second = intake.Docket(docket_of(300)), intake.Docket(docket_of(300))
    assert intake.check(first, 300, "OSVYCNA-15-2022") == intake.check(second, 300, "OSVYCNA-15-2022") == []
    assert first.answers.keys() == second.answers.keys()  # so a rerun asks the same numbers, from the cache


def test_tiny_dockets_have_no_room_for_holes():
    for n in (1, 2):
        docket = intake.Docket(docket_of(n))
        assert intake.check(docket, n, "seed") == []


def test_counting_a_senate_year():
    row = intake.count(docket_of(396), "OSVYCNA", 15, 2022, hint=388)
    assert (row["count"], row["flags"]) == (396, "")
    assert row["probes"] > 0
    assert intake.count(docket_of(0), "OSVYCNA", 15, 2022)["flags"] == "no case 1"


def test_a_lookup_that_keeps_failing_is_flagged_not_fatal():
    def exists(number):
        raise infosoud.LookupFailed("RIZENI_0001")

    row = intake.count(exists, "OSVYCNA", 15, 2022)
    assert row["count"] is None and row["flags"].startswith("error")


def test_the_summary_totals_by_year():
    rows = [
        {"court": "A", "senate": 1, "year": 2022, "count": 10, "probes": 12, "flags": ""},
        {"court": "B", "senate": 1, "year": 2022, "count": 5, "probes": 12, "flags": "hole:3"},
        {"court": "A", "senate": 1, "year": 2023, "count": None, "probes": 3, "flags": "error: x"},
    ]
    lines = intake.summary(rows)
    assert "Cases registered: 2022: 15 (2 courts)" in lines
    assert "Flagged senate-years: 2" in lines


@pytest.mark.parametrize(
    "seen, expected",
    [({3, 7}, list(range(1, 18))), ({112, 3}, list(range(1, 123))), (set(), list(range(1, 11)))],
)
def test_candidate_senates(seen, expected):
    assert senates.candidates(seen) == expected


def test_published_decisions_give_the_senates_and_the_hints(tmp_path):
    rows = [
        ("OSVYCNA", "C", 15, 384, 2022, 15),
        ("OSVYCNA", "C", 15, 384, 2022, 20),  # a second document in the same case
        ("OSVYCNA", "C", 15, 388, 2022, 16),
        ("OSVYCNA", "C", 9, 12, 2019, 30),  # a senate seen only before 2020
        ("OSVYCNA", "Co", 21, 5, 2022, 9),  # an appeal register
        (None, "C", 23, 88, 2012, 783),  # a regional court
    ]
    names = ["court", "register", "senate", "number", "year", "document"]
    columns = {name: [row[i] for row in rows] for i, name in enumerate(names)}
    columns |= {name: [None] * len(rows) for name in decisions.SCHEMA.names if name not in columns}
    path = tmp_path / "decisions.parquet"
    pyarrow.parquet.write_table(pyarrow.Table.from_pydict(columns, schema=decisions.SCHEMA), path)
    seen, hints = senates.published(path)
    assert seen == {"OSVYCNA": {15, 9}}
    assert hints == {("OSVYCNA", 2022, 15): (2, 388)}


def test_discovery_follows_the_rule_and_the_sweep():
    existing = {("A", 1, 2022), ("A", 2, 2022), ("A", 5, 2022), ("A", 14, 2022), ("A", 30, 2022)}

    def exists(court, senate, year):
        if senate == 13:
            raise infosoud.LookupFailed("RIZENI_0001")
        return (court, senate, year) in existing

    hints = {("A", 2022, 5): (3, 40), ("A", 2022, 7): (1, 2)}  # senate 7 published, but no case 1
    rows = senates.discover(
        exists, ["A"], {"A": {2, 5}}, hints, years=[2022], sweep=[("A", 2022, range(1, 40))]
    )
    summary = {row["senate"]: (row["case_1"], row["found_by"]) for row in rows}
    assert summary == {
        1: ("found", "rule"),
        2: ("found", "rule"),
        5: ("found", "rule"),
        7: ("not_found", "rule"),
        13: ("error", "rule"),
        14: ("found", "rule"),  # the highest seen, 5, plus the margin of 10, covers it
        30: ("found", "sweep"),
    }
    assert next(row for row in rows if row["senate"] == 5)["published_max"] == 40
