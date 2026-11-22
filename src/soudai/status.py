"""How far each stage has got, from the cache and the tables the stages have written.

    uv run soudai status

It only reads: it never creates the cache, and it's safe to run while a stage is running.
"""

import gzip
import re
import sqlite3
from collections import Counter

import pyarrow.parquet

from . import infosoud, paths, rozhodnuti
from .http import Response, UnexpectedResponse
from .reference import read_csv

# What each later stage writes. Nothing is there until its milestone runs.
DERIVED = [
    ("decisions", paths.DERIVED / "decisions.parquet"),
    ("senates", paths.DERIVED / "senates.csv"),
    ("intake", paths.DERIVED / "intake.csv"),
    ("sample", paths.DERIVED / "cases.parquet"),
    ("sample", paths.DERIVED / "events.parquet"),
]
DAY_INDEX = re.compile(re.escape(rozhodnuti.API) + r"/(\d{4})/(\d{1,2})$")
DAY_PAGE = re.compile(re.escape(rozhodnuti.API) + r"/(\d{4})/(\d{1,2})/(\d{1,2})\?page=(\d+)$")


def report(cache=paths.CACHE, reference=paths.REFERENCE, derived=DERIVED):
    """The status report, as lines of text."""
    lines = []
    if cache.exists():
        db = sqlite3.connect(cache)
        try:
            lines += _cache(db, cache) + _runs(db) + _decisions(db) + _lookups(db)
        finally:
            db.close()
    else:
        lines += [f"Cache: none yet ({cache})", ""]
    lines += _reference(reference) + _derived(derived)
    return lines


def _cache(db, cache):
    count = db.execute("SELECT count(*) FROM responses").fetchone()[0]
    megabytes = sum(path.stat().st_size for path in cache.parent.glob(cache.name + "*")) / 1e6
    hosts = Counter()
    for (url,) in db.execute("SELECT url FROM responses"):
        hosts[url.split("/")[2]] += 1
    lines = [f"Cache: {count:,} responses, {megabytes:.1f} MB ({cache})"]
    lines += [f"  {host}: {n:,}" for host, n in hosts.most_common()]
    return lines + [""]


def _runs(db, last=8):
    rows = db.execute(
        "SELECT id, stage, started_at, outcome, requests, cache_hits, failures, backend_version"
        " FROM runs ORDER BY id DESC LIMIT ?",
        (last,),
    ).fetchall()
    lines = [f"Last {len(rows)} runs:"] if rows else ["Runs: none yet"]
    for run_id, stage, started, outcome, requests, hits, failures, backend in rows:
        backend = f", backend {backend}" if backend else ""
        lines.append(
            f"  {run_id:>4} {started[:16]} {stage:<10} {outcome or 'running, or killed'}: "
            f"{requests:,} requests, {hits:,} from the cache, {failures} failures{backend}"
        )
    return lines + [""]


def _decisions(db):
    """Published decisions (milestone 3): the day pages cached, against the days in the month indexes."""
    expected, indexes, unreadable = {}, 0, 0
    cached = Counter()
    for url, status, content, content_type in db.execute(
        "SELECT url, status, content, content_type FROM responses WHERE url LIKE ?", (rozhodnuti.API + "/%",)
    ):
        if status != 200:
            continue
        if DAY_INDEX.match(url):
            try:
                rows = rozhodnuti.parse_index(_response(url, status, content, content_type), "datum")
            except UnexpectedResponse:
                unreadable += 1
                continue
            indexes += 1
            expected |= {row["datum"]: rozhodnuti.pages(row["pocet"]) for row in rows}
        elif match := DAY_PAGE.match(url):
            year, month, day, _ = (int(group) for group in match.groups())
            cached[f"{year:04d}-{month:02d}-{day:02d}"] += 1
    complete = sum(1 for day, pages in expected.items() if cached[day] >= pages)
    lines = [
        "Published decisions (milestone 3):",
        f"  {len(expected):,} days in the {indexes:,} cached month indexes, {complete:,} of them "
        f"fully cached; {sum(cached.values()):,} of {sum(expected.values()):,} day pages",
    ]
    if unreadable:
        lines.append(f"  {unreadable:,} cached month indexes don't parse, and will be fetched again")
    return lines + [""]


def _lookups(db):
    """Case lookups (milestones 4 and 5), by the case number's year and the outcome."""
    url = infosoud.API + "rizeni/vyhledej"
    by_year = {}
    found = db.execute(
        "SELECT json_extract(body, '$.rocnik'), count(*) FROM responses"
        " WHERE url = ? AND status = 200 GROUP BY 1",
        (url,),
    )
    for year, n in found:
        by_year.setdefault(year, Counter())["found"] += n
    others = db.execute(
        "SELECT json_extract(body, '$.rocnik'), status, content, content_type FROM responses"
        " WHERE url = ? AND status != 200",
        (url,),
    )
    for year, status, content, content_type in others:
        try:
            outcome = infosoud.parse_lookup(_response(url, status, content, content_type)).outcome
        except UnexpectedResponse:
            outcome = "unexpected"
        by_year.setdefault(year, Counter())[outcome.replace("_", " ")] += 1
    if not by_year:
        return ["Case lookups (milestones 4 and 5): none yet", ""]
    lines = ["Case lookups (milestones 4 and 5), by the case number's year:"]
    for year in sorted(by_year, key=str):
        counts = ", ".join(f"{n:,} {outcome}" for outcome, n in sorted(by_year[year].items()))
        lines.append(f"  {year}: {counts}")
    return lines + [""]


def _response(url, status, content, content_type):
    return Response(url, status, gzip.decompress(content), content_type, "", from_cache=True)


def _reference(folder):
    lines = ["Reference tables:"]
    courts, events = folder / "courts.csv", folder / "events.csv"
    lines.append(
        f"  courts.csv: {_csv_rows(courts):,} courts" if courts.exists() else "  courts.csv: not yet"
    )
    if events.exists():
        kinds = Counter(row["kind"] for row in read_csv(events.name, folder))
        lines.append(f"  events.csv: {kinds['event']} event codes, {kinds['status']} statuses")
    else:
        lines.append("  events.csv: not yet")
    return lines + [""]


def _derived(derived):
    lines = ["Derived tables:"]
    for stage, path in derived:
        if not path.exists():
            lines.append(f"  {path.name}: not yet ({stage})")
        elif path.suffix == ".parquet":
            lines.append(f"  {path.name}: {pyarrow.parquet.read_metadata(path).num_rows:,} rows")
        else:
            lines.append(f"  {path.name}: {_csv_rows(path):,} rows")
    return lines


def _csv_rows(path):
    with open(path, encoding="utf-8") as file:
        return sum(1 for _ in file) - 1


def run():
    print("\n".join(report()))
    return 0
