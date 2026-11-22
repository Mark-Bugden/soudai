"""`soudai status`, on an empty project and on a small cache."""

import json

from conftest import load
from test_http import FakeClock, FakeReply, FakeSession

from soudai import http, infosoud, rozhodnuti, status


def test_with_nothing_yet_it_says_so_and_creates_nothing(tmp_path):
    cache = tmp_path / "raw" / "cache.sqlite"
    derived = [("intake", tmp_path / "intake.csv")]
    lines = status.report(cache, tmp_path / "reference", derived)
    assert any(line.startswith("Cache: none yet") for line in lines)
    assert "  courts.csv: not yet" in lines
    assert "  intake.csv: not yet (intake)" in lines
    assert not cache.exists()


def test_it_counts_runs_day_pages_and_lookups_by_outcome(tmp_path):
    days, _ = load("rozhodnuti/days_2023_03.json")
    page, _ = load("rozhodnuti/day_2023_03_15_page_0.json")
    found, _ = load("infosoud/case_found.json")
    missing, _ = load("infosoud/case_not_found.json")
    lookup = infosoud.API + "rizeni/vyhledej"
    replies = [FakeReply(record["status"], _content(record)) for record in (days, page, found, missing)]
    replies += [
        FakeReply(200, b"<!doctype html>", "text/html"),  # a month index that's an outage page
        FakeReply(400, json.dumps({"message": "RIZENI_0001"}).encode()),
        FakeReply(400, json.dumps({"message": "RIZENI_VALIDATION_0002"}).encode()),
    ]
    clock = FakeClock()
    session = FakeSession(replies)
    client = http.Client("test", tmp_path / "cache.sqlite", tmp_path / "logs", session, clock, clock.sleep)
    with client:
        rozhodnuti.days(client, 2023, 3)
        client.get(page["url"])
        client.post(lookup, found["body"])
        client.post(lookup, missing["body"])
        client.get(rozhodnuti.API + "/2023/4")
        client.post(lookup, infosoud.case_request("KSVYCHK", "OSVYCNA", "C", 15, 1, 2022))
        client.post(lookup, infosoud.case_request("KSVYCHK", "OSVYCNA", "C", 15, 2, 2022))
    intake = "court,senate,year,count\nA,1,2022,10\nA,2,2022,12\n"
    (tmp_path / "intake.csv").write_text(intake, encoding="utf-8")

    lines = status.report(tmp_path / "cache.sqlite", tmp_path, [("intake", tmp_path / "intake.csv")])
    text = "\n".join(lines)
    assert "Cache: 7 responses" in text
    assert "test       finished: 7 requests, 0 from the cache, 0 failures" in text
    assert "27 days in the 1 cached month indexes, 0 of them fully cached; 1 of 97 day pages" in text
    assert "1 cached month indexes don't parse, and will be fetched again" in text
    assert "  2022: 1 error, 1 found, 1 not found, 1 unexpected" in text
    assert "  intake.csv: 2 rows" in text


def _content(record):
    return json.dumps(record["response"], ensure_ascii=False).encode("utf-8")
