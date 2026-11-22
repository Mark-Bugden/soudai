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


def test_it_counts_runs_day_pages_and_lookups(tmp_path):
    days, _ = load("rozhodnuti/days_2023_03.json")
    page, _ = load("rozhodnuti/day_2023_03_15_page_0.json")
    found, _ = load("infosoud/case_found.json")
    missing, _ = load("infosoud/case_not_found.json")
    replies = [FakeReply(record["status"], _content(record)) for record in (days, page, found, missing)]
    clock = FakeClock()
    session = FakeSession(replies)
    client = http.Client("test", tmp_path / "cache.sqlite", tmp_path / "logs", session, clock, clock.sleep)
    with client:
        rozhodnuti.days(client, 2023, 3)
        client.get(page["url"])
        client.post(infosoud.API + "rizeni/vyhledej", found["body"])
        client.post(infosoud.API + "rizeni/vyhledej", missing["body"])
    (tmp_path / "intake.csv").write_text(
        "court,senate,year,count\nA,1,2022,10\nA,2,2022,12\n", encoding="utf-8"
    )

    lines = status.report(tmp_path / "cache.sqlite", tmp_path, [("intake", tmp_path / "intake.csv")])
    text = "\n".join(lines)
    assert "Cache: 4 responses" in text
    assert "test       finished: 4 requests, 0 from the cache, 0 failures" in text
    assert "27 days in the 1 cached month indexes, 0 of them fully cached; 1 of 97 day pages" in text
    assert "  2022: 1 HTTP 400, 1 found" in text
    assert "  intake.csv: 2 rows" in text


def _content(record):
    return json.dumps(record["response"], ensure_ascii=False).encode("utf-8")
