"""Senates (milestone 4): which senates of each court registered civil cases in each year, 2020–2025.

The candidates for a court are the senates seen in its published register C decisions (any year), plus
every senate from 1 to the highest seen below 100, + 10. Senates above 100 come in series by the
hundred (105–118, 205–218 and 305–317 at Ústí nad Orlicí, 2104–2119 in Brno), so each hundred in which
at least 3 senates are seen is probed the same way: 301 to its highest + 10, say. A hundred with fewer
is a stray (11297 at Náchod, probably a typo), and only the senates seen in it are probed. A
senate-year exists if its case number 1 does. For a few courts and one year, a sweep of senates 1–999
checks that the rule misses nothing.

Writes data/derived/senates.csv: one row per senate-year whose case 1 exists, or that has published
decisions without a case 1 (flagged), with what the published decisions say about it: how many of its
cases were published, and the highest number among them (the hint for `soudai intake`).

    uv run soudai senates    # needs data/derived/decisions.parquet, from `soudai decisions`
"""

from collections import defaultdict

import pyarrow.parquet

from . import decisions, infosoud, paths, reference
from .http import Client

PATH = paths.DERIVED / "senates.csv"
COLUMNS = ["court", "year", "senate", "case_1", "published_cases", "published_max", "found_by"]
YEARS = range(2020, 2026)
MARGIN = 10
SERIES = 3  # the senates that must be seen in a hundred above the first for it to be probed in full
# The wide sweep: courts with branches or senate series, a Prague court and a small court.
SWEEP_COURTS = ["OSSEMKA", "OSJIMBM", "OSVYCUO", "OSPHA01", "OSSEMJE"]
SWEEP_YEAR = 2023
SWEEP_SENATES = range(1, 1000)


def published(path=decisions.PATH):
    """What the published decisions say, for register C at district-level courts:
    ({court: senates seen in any year}, {(court, year, senate): (distinct cases, highest number)})."""
    names = ["court", "register", "senate", "number", "year"]
    table = pyarrow.parquet.read_table(path, columns=names)
    seen, cases = defaultdict(set), defaultdict(set)
    for court, register, senate, number, year in zip(
        *(table[name].to_pylist() for name in names), strict=True
    ):
        if court and register == "C" and senate is not None:
            seen[court].add(senate)
            if year in YEARS:
                cases[court, year, senate].add(number)
    return seen, {key: (len(numbers), max(numbers)) for key, numbers in cases.items()}


def candidates(seen):
    """The senates to probe for a court, from those seen in its published decisions."""
    hundreds = defaultdict(set)
    for senate in seen:
        hundreds[senate // 100].add(senate)
    probe = set(seen) | set(range(1, max(hundreds[0], default=0) + MARGIN + 1))
    for hundred, senates in hundreds.items():
        if hundred and len(senates) >= SERIES:
            probe |= set(range(100 * hundred + 1, max(senates) + MARGIN + 1))
    return sorted(probe)


def discover(exists, courts, seen, hints, years=YEARS, sweep=()):
    """senates.csv's rows, from `exists(court, senate, year)`: whether a senate-year's case 1 exists.
    `sweep` is a list of (court, year, senates) to probe in full, on top of the rule."""
    rows = {}
    for court in courts:
        for year in years:
            for senate in candidates(seen.get(court, ())):
                rows[court, year, senate] = _row(exists, court, year, senate, hints, "rule")
    for court, year, senates in sweep:
        for senate in senates:
            if (court, year, senate) not in rows:
                rows[court, year, senate] = _row(exists, court, year, senate, hints, "sweep")
    return [row for _, row in sorted(rows.items()) if row["case_1"] != "not_found" or row["published_cases"]]


def _row(exists, court, year, senate, hints, found_by):
    try:
        case_1 = "found" if exists(court, senate, year) else "not_found"
    except infosoud.LookupFailed:
        case_1 = "error"
    cases, highest = hints.get((court, year, senate), ("", ""))
    return {
        "court": court,
        "year": year,
        "senate": senate,
        "case_1": case_1,
        "published_cases": cases,
        "published_max": highest,
        "found_by": found_by,
    }


def run():
    courts = {court["code"]: court for court in reference.courts()}
    seen, hints = published()
    sweep = [(court, SWEEP_YEAR, SWEEP_SENATES) for court in SWEEP_COURTS]
    with Client("senates") as client:
        infosoud.backend_version(client)
        probes = sum(len(candidates(seen.get(court, ()))) for court in courts) * len(YEARS)
        client.log.info(f"{probes:,} senate-years to probe by the rule, and a sweep of {len(sweep)} courts")
        done = set()

        def exists(court, senate, year):
            if court not in done and len(done) % 5 == 0:
                client.log.info(f"{len(done)} of {len(courts)} courts; {client.requests:,} requests")
            done.add(court)
            return infosoud.exists(client, courts[court]["regional_code"], court, "C", senate, 1, year)

        rows = discover(exists, courts, seen, hints, sweep=sweep)
    reference.write_csv(PATH.name, rows, COLUMNS, folder=PATH.parent)
    print("\n".join(summary(rows, sweep)))
    return 0


def summary(rows, sweep):
    found = [row for row in rows if row["case_1"] == "found"]
    by_year = defaultdict(int)
    for row in found:
        by_year[row["year"]] += 1
    swept = [row for row in found if row["found_by"] == "sweep"]
    unexplained = [row for row in rows if row["case_1"] != "found"]
    lines = [
        f"{len(found):,} senate-years with a case 1: "
        + ", ".join(f"{year}: {n:,}" for year, n in sorted(by_year.items())),
        f"Found only by the sweep of {', '.join(court for court, _, _ in sweep)}: {len(swept)}",
        f"Published decisions without a case 1, or errors: {len(unexplained)}",
    ]
    lines += [
        f"  {row['court']} {row['senate']} C {row['year']}: {row['found_by']}, case 1 {row['case_1']}"
        for row in swept + unexplained
    ][:60]
    return lines
