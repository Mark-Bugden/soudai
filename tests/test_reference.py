"""Checks on the hand-checked tables in reference/: courts.csv, events.csv and sources.json."""

import json
from collections import Counter

import pytest
from conftest import FIXTURES

from soudai import courts, events, infosoud, paths, reference

# District courts per regional court, as infosoud listed them on 2026-11-22.
COURTS_PER_REGION = {
    "KSJIMBM": 14,  # Brno
    "KSJICCB": 8,  # České Budějovice
    "KSVYCHK": 11,  # Hradec Králové
    "KSSEMOS": 11,  # Ostrava
    "KSZPCPM": 10,  # Plzeň
    "KSSTCAB": 12,  # Praha (the regional court for Central Bohemia)
    "KSSCEUL": 10,  # Ústí nad Labem
    "MSPHAAB": 10,  # Městský soud Praha: Prague's ten district courts
}


@pytest.fixture(scope="module")
def court_rows():
    return reference.courts()


@pytest.fixture(scope="module")
def event_rows():
    return reference.events()


def rozhodnuti_names(court_rows):
    return {name: row["code"] for row in court_rows for name in row["rozhodnuti_names"].split("; ")}


def test_there_are_86_district_level_courts(court_rows):
    assert len(court_rows) == 86
    assert len({row["code"] for row in court_rows}) == 86
    assert Counter(row["regional_code"] for row in court_rows) == COURTS_PER_REGION


def test_every_court_has_every_column(court_rows):
    for row in court_rows:
        assert list(row) == courts.COLUMNS
        assert all(row.values()), row


def test_each_rozhodnuti_name_belongs_to_one_court(court_rows):
    names = [name for row in court_rows for name in row["rozhodnuti_names"].split("; ")]
    assert len(names) == len(set(names)) == 89  # 86 courts, three with a branch


def test_each_area_is_served_by_one_court(court_rows):
    areas = [row["area"] for row in court_rows]
    assert len(set(areas)) == 86
    assert sum(area.startswith("Praha ") for area in areas) == 10


@pytest.mark.parametrize(
    "name, area",
    [
        ("Okresní soud Náchod", "Náchod"),
        ("Městský soud Brno", "Brno-město"),
        ("Okresní soud Ostrava", "Ostrava-město"),
        ("Okresní soud Plzeň-Město", "Plzeň-město"),
        ("Okresní soud Praha-Východ", "Praha-východ"),
        ("Okresní soud Brno-venkov", "Brno-venkov"),
        ("Okresní soud Frýdek-Místek", "Frýdek-Místek"),
        ("Obvodní soud Praha 10", "Praha 10"),
    ],
)
def test_areas(name, area):
    assert courts.area(name) == area


def test_every_district_court_on_a_real_day_page_maps_to_a_court(court_rows):
    page = json.loads((FIXTURES / "rozhodnuti" / "day_2023_03_15_page_0.json").read_text(encoding="utf-8"))
    names = rozhodnuti_names(court_rows)
    district = {item["soud"] for item in page["response"]["items"]} - {"(nezadán)"}
    district = {
        name
        for name in district
        if not name.startswith(("Krajský", "Vrchní", "Nejvyšší", "Městský soud v Praze"))
    }
    assert district and district <= names.keys(), district - names.keys()


def test_the_seed_parser_reads_codes_not_regional_codes():
    seed = """
- name: "Krajský soud v Ostravě"
  typSoudu: "os"
  krajOrg: "KSSEMOS"
  Org: ""

- name: "Okresní soud v Bruntále"
  typSoudu: "os"
  krajOrg: "KSSEMOS"
  Org: "OSSEMBR"

- name: "Okresní soud v Bruntále, pobočka Krnov"
  typSoudu: "os"
  krajOrg: "KSSEMOS"
  Org: "OSSEMBR"
"""
    assert courts.parse_seed(seed) == {
        "OSSEMBR": ["Okresní soud v Bruntále", "Okresní soud v Bruntále, pobočka Krnov"]
    }


def test_compare_reports_new_gone_and_changed_courts():
    row = {"code": "A", "regional_code": "R", "name": "Okresní soud A", "rozhodnuti_names": "a", "area": "A"}
    old = [row, {**row, "code": "B", "name": "Okresní soud B"}]
    new = [{**row, "name": "Okresní soud A2"}, {**row, "code": "C", "name": "Okresní soud C"}]
    assert courts.compare(old, new) == [
        "new: C Okresní soud C",
        "gone: B Okresní soud B",
        "changed: A name: 'Okresní soud A' -> 'Okresní soud A2'",
    ]


def test_the_event_codes_are_exactly_the_apps(event_rows):
    chunk = (FIXTURES / "infosoud" / "labels_chunk.js").read_text(encoding="utf-8")
    labels = infosoud.event_labels(chunk)
    rows = {row["code"]: row for row in event_rows if row["kind"] == "event"}
    assert rows.keys() == labels.keys()
    for code, label in labels.items():
        assert rows[code]["label_cs"] == label["label"]


def test_every_row_is_glossed_in_english(event_rows):
    assert {row["kind"] for row in event_rows} == {"event", "status"}
    assert all(row["gloss_en"] for row in event_rows), [
        row["code"] for row in event_rows if not row["gloss_en"]
    ]


def test_every_event_and_status_in_the_saved_cases_is_in_the_table(event_rows):
    codes = {(row["kind"], row["code"]) for row in event_rows}
    for path in (FIXTURES / "infosoud").glob("case_*.json"):
        case = json.loads(path.read_text(encoding="utf-8"))["response"]
        if "udalosti" not in case:
            continue
        assert ("status", case["stav"]) in codes, (path.name, case["stav"])
        for event in case["udalosti"]:
            assert ("event", event["udalost"]) in codes, (path.name, event["udalost"])


def test_refreshing_the_labels_keeps_the_glosses_and_statuses():
    existing = [
        {"kind": "event", "code": "ZAHAJ_RIZ", "gloss_en": "Case filed"},
        {"kind": "event", "code": "OLD_CODE", "gloss_en": "Gone"},
        {"kind": "status", "code": "nevyřízená věc", "gloss_en": "Open"},
    ]
    labels = {
        "ZAHAJ_RIZ": {"label": "Zahájení řízení", "tooltip": "", "description": ""},
        "NEW_CODE": {"label": "Nový", "tooltip": "", "description": ""},
    }
    rows = events.merge(labels, existing)
    assert [(row["kind"], row["code"], row["gloss_en"]) for row in rows] == [
        ("event", "NEW_CODE", ""),
        ("event", "ZAHAJ_RIZ", "Case filed"),
        ("status", "nevyřízená věc", "Open"),
    ]


def test_sources_record_the_endpoints_backend_and_seed():
    sources = json.loads((paths.REFERENCE / "sources.json").read_text(encoding="utf-8"))
    assert sources["infosoud"]["backend_version"]
    assert sources["infosoud"]["checked"] and sources["rozhodnuti"]["checked"]
    assert sources["court_map"]["commit"] in sources["court_map"]["url"]
    assert sources["court_map"]["commit"] == courts.SEED_COMMIT
