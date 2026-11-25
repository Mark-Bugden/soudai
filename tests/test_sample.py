"""The timeline sample: the allocation, the order numbers are tried in, the draw, and the parsed rows."""

import json
from datetime import date

import pytest
from conftest import FIXTURES

from soudai import infosoud, intake, sample


def case_record(name):
    return json.loads((FIXTURES / "infosoud" / name).read_text(encoding="utf-8"))["response"]


@pytest.mark.parametrize(
    "counts",
    [{1: 300, 2: 300, 3: 150}, {9: 363, 10: 224, 11: 5, 12: 1}, {15: 396}, {1: 2000, 2: 1, 3: 1}],
)
def test_the_allocation_is_proportional_and_gives_every_senate_a_case(counts):
    wanted = sample.allocation(counts, 400)
    assert wanted.keys() == counts.keys()
    assert all(1 <= wanted[s] <= counts[s] for s in counts)
    total = sum(counts.values())
    assert min(400, total) <= sum(wanted.values()) <= 400 + len(counts)  # the minimum of 1 can add a few
    total = sum(counts.values())
    assert all(
        abs(wanted[s] - min(counts[s], 400 * counts[s] / total)) < 1.5 for s in counts if counts[s] > 4
    )


def test_the_allocation_never_asks_for_more_than_a_senate_has():
    assert sample.allocation({1: 3, 2: 2}, 400) == {1: 3, 2: 2}


@pytest.mark.parametrize("count", [1, 2, 3, 4, 50, 396])
def test_the_order_starts_with_intakes_probes_and_covers_every_number(count):
    numbers = sample.order("OSVYCNA", 15, 2022, count)
    probes = intake.probe_numbers(count, "OSVYCNA-15-2022")
    assert numbers[: len(probes)] == probes
    assert sorted(numbers) == list(range(1, count + 1))
    assert numbers == sample.order("OSVYCNA", 15, 2022, count)  # seeded, so a rerun asks the same
    if count > 10:
        assert numbers != sample.order("OSVYCNA", 16, 2022, count)


def finder(hidden=(), failing=(), wrong=()):
    asked = []

    def find(number):
        asked.append(number)
        if number in failing:
            raise infosoud.LookupFailed(str(number))
        if number in wrong:
            raise infosoud.WrongCase(str(number))
        return None if number in hidden else {"number": number}

    find.asked = asked
    return find


def test_a_draw_skips_hidden_and_failing_numbers_and_tries_the_next():
    numbers = sample.order("OSVYCNA", 15, 2022, 100)
    hidden, failing = {numbers[0], numbers[5]}, {numbers[6]}
    found, n_hidden, failed = sample.draw(finder(hidden, failing), "OSVYCNA", 15, 2022, 100, wanted=10)
    assert len(found) == 10
    assert (n_hidden, failed) == (2, [numbers[6]])
    assert [n for n, _, _ in found] == [n for n in numbers[:13] if n not in hidden | failing]


def test_a_draw_keeps_all_the_probes_and_marks_them():
    found, _, _ = sample.draw(finder(), "OSVYCNA", 15, 2022, 100, wanted=1)
    probes = intake.probe_numbers(100, "OSVYCNA-15-2022")
    assert [(n, source) for n, _, source in found] == [(n, "probe") for n in probes]
    found, _, _ = sample.draw(finder(), "OSVYCNA", 15, 2022, 100, wanted=5)
    assert [source for _, _, source in found] == ["probe"] * 3 + ["sample"] * 2


def test_a_draw_stops_when_the_numbers_run_out():
    found, hidden, _ = sample.draw(finder(hidden={2}), "OSVYCNA", 15, 2022, 3, wanted=3)
    assert (len(found), hidden) == (2, 1)


def test_targets_come_from_intake_csv(tmp_path):
    path = tmp_path / "intake.csv"
    path.write_text(
        "court,senate,year,count,published_cases,published_max,probes,flags\n"
        "A,1,2022,300,,,12,\nA,2,2022,100,,,12,\nA,3,2022,0,,,2,no case 1\nB,1,2022,50,,,10,\n",
        encoding="utf-8",
    )
    assert sample.targets(path, total=40) == [
        ("A", 1, 2022, 300, 30),
        ("A", 2, 2022, 100, 10),
        ("B", 1, 2022, 50, 40),
    ]


def test_a_disposed_case_becomes_a_row_and_its_events():
    case = case_record("case_disposed.json")
    row = sample.case_row("OSVYCNA", case["cislo"], case["rocnik"], case["bcVec"], case, 12.5, "sample")
    filed = next(e["datum"] for e in infosoud.sorted_events(case) if e["udalost"] == "ZAHAJ_RIZ")
    assert row["filing_date"] == date.fromisoformat(filed[:10])
    assert row["status"] == case["stav"]
    assert row["status_date"] is not None and row["valid_to"] == date.fromisoformat(case["platneK"][:10])
    assert (row["weight"], row["source"], row["linked"]) == (12.5, "sample", len(case["navazneVeci"]))
    events = sample.event_rows("OSVYCNA", case["cislo"], case["rocnik"], case["bcVec"], case)
    assert [e["code"] for e in events] == [e["udalost"] for e in infosoud.sorted_events(case)]
    assert all(isinstance(e["date"], date) for e in events)


def test_a_cancelled_hearing_is_kept_and_marked():
    case = case_record("case_cancelled_hearing.json")
    events = sample.event_rows("OSVYCNA", case["cislo"], case["rocnik"], case["bcVec"], case)
    assert any(e["cancelled"] for e in events) and not all(e["cancelled"] for e in events)


@pytest.mark.parametrize(
    "text, day", [("19.10.2026", date(2026, 10, 19)), ("1.2.2023", date(2023, 2, 1)), (None, None)]
)
def test_czech_dates(text, day):
    assert sample._czech_date(text) == day


def test_the_weights_add_up_to_the_counts(monkeypatch):
    def find_case(client, regional, court, register, senate, number, year):
        return (
            None
            if (senate, number) == (1, hidden)
            else {"stav": "x", "udalosti": [], "platneK": "2026-11-21T18:30:01+01:00"}
        )

    hidden = sample.order("A", 1, 2022, 300)[3]  # the first pick after the probes
    monkeypatch.setattr(infosoud, "find_case", find_case)
    todo = [("A", 1, 2022, 300, 30), ("A", 2, 2022, 100, 10), ("A", 3, 2022, 2, 1)]
    courts = {"A": {"regional_code": "KS"}}
    cases, events, tally = sample.sample_all(None, todo, courts)
    assert len(cases) == 41 and tally["hidden"] == 1
    assert sum(row["weight"] for row in cases) == pytest.approx(402)
    assert events == []
    _, _, quiet = sample.sample_all(None, todo, courts, keep=False)
    assert quiet["probe"] + quiet["sample"] == len(cases)


def test_a_record_for_another_case_is_skipped_like_a_failure():
    numbers = sample.order("OSSTCNB", 5, 2020, 300)
    found, hidden, failed = sample.draw(finder(wrong={numbers[3]}), "OSSTCNB", 5, 2020, 300, wanted=5)
    assert (len(found), hidden, failed) == (5, 0, [numbers[3]])


def test_an_appeal_is_marked_with_the_regional_courts_case():
    case = case_record("case_appealed.json")  # 8 C 1/2023 at Náchod, appealed to Hradec Králové
    events = sample.event_rows("OSVYCNA", 8, 2023, 1, case)
    linked = [(e["code"], e["linked_court"], e["linked_case"]) for e in events if e["linked_court"]]
    assert linked == [
        ("ODVOLANI", "KSVYCHK", next(_case(e) for e in case["udalosti"] if e["udalost"] == "ODVOLANI"))
    ]
    assert all(e["linked_case"] is None for e in events if e["code"] != "ODVOLANI")


def _case(event):
    mark = event["znackaId"]
    return f"{mark['cisloSenatu']} {mark['druhVeci']} {mark['bcVec']}/{mark['rocnik']}"
