"""How far each stage has got, from the cache and the tables the stages have written.

    uv run soudai status

It only reads: it never creates the cache, and it's safe to run while a stage is running.
"""

import gzip
import json
import re
import sqlite3
from collections import Counter

import pyarrow.parquet

from . import infosoud, paths, rozhodnuti
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
    expected = {}
    for url, content in db.execute(
        "SELECT url, content FROM responses WHERE url LIKE ? AND status = 200", (rozhodnuti.API + "/%",)
    ):
        if DAY_INDEX.match(url):
            for row in json.loads(gzip.decompress(content)):
                expected[row["datum"]] = rozhodnuti.pages(row["pocet"])
    cached = Counter()
    for (url,) in db.execute(
        "SELECT url FROM responses WHERE url LIKE ? AND status = 200", (rozhodnuti.API + "/%",)
    ):
        if match := DAY_PAGE.match(url):
            year, month, day, _ = (int(group) for group in match.groups())
            cached[f"{year:04d}-{month:02d}-{day:02d}"] += 1
    complete = sum(1 for day, pages in expected.items() if cached[day] >= pages)
    return [
        "Published decisions (milestone 3):",
        f"  {len(expected):,} days in the {_count_indexes(db):,} cached month indexes, {complete:,} of them "
        f"fully cached; {sum(cached.values()):,} of {sum(expected.values()):,} day pages",
        "",
    ]


def _count_indexes(db):
    urls = db.execute("SELECT url FROM responses WHERE url LIKE ?", (rozhodnuti.API + "/%",))
    return sum(1 for (url,) in urls if DAY_INDEX.match(url))


def _lookups(db):
    """Case lookups (milestones 4 and 5), by filing year and outcome."""
    rows = db.execute(
        "SELECT json_extract(body, '$.rocnik'), status, count(*) FROM responses WHERE url = ? GROUP BY 1, 2",
        (infosoud.API + "rizeni/vyhledej",),
    ).fetchall()
    if not rows:
        return ["Case lookups (milestones 4 and 5): none yet", ""]
    by_year = {}
    for year, status, n in rows:
        by_year.setdefault(year, Counter())["found" if status == 200 else f"HTTP {status}"] += n
    lines = ["Case lookups (milestones 4 and 5), by filing year:"]
    for year in sorted(by_year, key=str):
        counts = ", ".join(f"{n:,} {outcome}" for outcome, n in sorted(by_year[year].items()))
        lines.append(f"  {year}: {counts}")
    return lines + [""]


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
