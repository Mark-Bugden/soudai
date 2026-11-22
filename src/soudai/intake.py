"""Exact intake (milestone 4): how many civil cases each senate registered each year, from its docket.

A senate numbers its register C cases 1, 2, 3, ... afresh each year, so if the docket has no gaps, its
highest existing number is the number of cases it registered that year. The search:

- **Top.** From a hint (the highest number seen in published decisions, or 1), probe upwards in steps
  of 16, 32, 64, ... until a number is missing, then binary search between the last that exists and
  the first that doesn't.
- **Islands.** Probe the top + 1, 2, 3, 10 and 25. Any that exists means the docket goes on past a gap.
- **Holes.** Probe 3 numbers below the top, drawn with a seed made from the court, senate and year, so
  a rerun asks the same ones and the cache answers.

A senate-year with an island or a hole is flagged, and its count isn't trusted until it's investigated
(the plan: settle it with Mark before milestone 5).

    uv run soudai intake    # needs data/derived/senates.csv, from `soudai senates`
"""

import csv
import random
from collections import defaultdict

from . import infosoud, paths, reference
from .http import Client

PATH = paths.DERIVED / "intake.csv"
COLUMNS = ["court", "senate", "year", "count", "published_cases", "published_max", "probes", "flags"]
FIRST_STEP = 16
ABOVE = (1, 2, 3, 10, 25)
HOLES = 3


class Docket:
    """One senate-year's docket, asked through `exists(number)`, which is called once per number."""

    def __init__(self, exists):
        self.exists = exists
        self.answers = {}

    def __call__(self, number):
        if number not in self.answers:
            self.answers[number] = self.exists(number)
        return self.answers[number]


def find_top(docket, hint=None):
    """The highest number in a docket with no gaps: 0 if number 1 doesn't exist."""
    if not docket(1):
        return 0
    low, high = 1, None
    if hint and hint > 1:
        if docket(hint):
            low = hint
        else:
            high = hint
    step = FIRST_STEP
    while high is None:
        if docket(low + step):
            low += step
            step *= 2
        else:
            high = low + step
    while high - low > 1:
        middle = (low + high) // 2
        if docket(middle):
            low = middle
        else:
            high = middle
    return low


def check(docket, top, seed):
    """Flags for numbers above the top that exist (islands) and numbers below it that don't (holes)."""
    flags = [f"island:{top + d}" for d in ABOVE if docket(top + d)]
    below = range(2, top)
    for number in sorted(random.Random(seed).sample(below, min(HOLES, len(below)))):
        if not docket(number):
            flags.append(f"hole:{number}")
    return flags


def count(exists, court, senate, year, hint=None):
    """One senate-year's row of intake.csv, apart from the published columns."""
    docket = Docket(exists)
    try:
        top = find_top(docket, hint)
        flags = check(docket, top, f"{court}-{senate}-{year}") if top else ["no case 1"]
    except infosoud.LookupFailed as error:
        top, flags = None, [f"error: {error}"]
    return {
        "court": court,
        "senate": senate,
        "year": year,
        "count": top,
        "probes": len(docket.answers),
        "flags": "; ".join(flags),
    }


def read_senates(path=paths.DERIVED / "senates.csv"):
    """The senate-years whose case 1 exists, from `soudai senates`."""
    with open(path, encoding="utf-8", newline="") as file:
        return [row for row in csv.DictReader(file) if row["case_1"] == "found"]


def run():
    courts = {court["code"]: court for court in reference.courts()}
    senates = read_senates()
    rows = []
    with Client("intake") as client:
        infosoud.backend_version(client)
        client.log.info(f"{len(senates):,} senate-years to count")
        for i, row in enumerate(senates, 1):
            court, senate, year = row["court"], int(row["senate"]), int(row["year"])
            regional = courts[court]["regional_code"]

            def exists(number, court=court, senate=senate, year=year, regional=regional):
                return infosoud.exists(client, regional, court, "C", senate, number, year)

            hint = int(row["published_max"]) if row["published_max"] else None
            counted = count(exists, court, senate, year, hint)
            counted |= {"published_cases": row["published_cases"], "published_max": row["published_max"]}
            rows.append(counted)
            if counted["flags"]:
                client.log.warning(f"{court} {senate} C {year}: {counted['flags']}")
            if i % 50 == 0 or i == len(senates):
                client.log.info(f"{i:,} of {len(senates):,} senate-years; {client.requests:,} requests")
    reference.write_csv(PATH.name, rows, COLUMNS, folder=PATH.parent)
    print("\n".join(summary(rows)))
    return 0


def summary(rows):
    """Totals by year and nationally, the probes used, and every flag."""
    by_year, courts_by_year = defaultdict(int), defaultdict(set)
    for row in rows:
        if row["count"]:
            by_year[row["year"]] += row["count"]
            courts_by_year[row["year"]].add(row["court"])
    flagged = [row for row in rows if row["flags"]]
    probes = sum(row["probes"] for row in rows)
    lines = [
        f"{len(rows):,} senate-years counted with {probes:,} probes "
        f"({probes / max(len(rows), 1):.1f} each, cached ones included)",
        "Cases registered: "
        + ", ".join(
            f"{year}: {n:,} ({len(courts_by_year[year])} courts)" for year, n in sorted(by_year.items())
        ),
        f"National total, all years: {sum(by_year.values()):,}",
        f"Flagged senate-years: {len(flagged):,}",
    ]
    lines += [f"  {row['court']} {row['senate']} C {row['year']}: {row['flags']}" for row in flagged[:50]]
    return lines
