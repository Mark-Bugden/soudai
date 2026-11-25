"""The timeline sample (milestone 5): the full history of a random sample of the cases counted in step 4.

The sample is drawn by senate-year (one senate's cases in one year). Each court-year's 400 cases are
split between its senates in proportion to the cases each registered, with at least 1 each. Intake's
hole probes (3 random numbers below each senate-year's top) are counted in, since their timelines are
already in the cache. So a senate-year's numbers are tried in this order: the probes first, then the
rest of 1 to its count, shuffled with a seed made from the court, senate and year. A number infosoud
hides is skipped, and the next one is tried, and so is one whose record is for another case (see
`infosoud.WrongCase`). Each sampled case stands for count / sampled cases of its
senate-year: that's its weight.

Writes data/derived/cases.parquet (one row per sampled case) and data/derived/events.parquet (one row
per event, cancelled ones included and marked).

    uv run soudai sample                 # fetch what isn't cached, then parse
    uv run soudai sample --parse-only    # parse what's cached, fetching nothing
"""

import csv
import random
from collections import Counter, defaultdict
from datetime import date

import pyarrow
import pyarrow.parquet

from . import infosoud, intake, paths, reference
from .http import CacheReader, Client

PER_COURT_YEAR = 400
CASES = paths.DERIVED / "cases.parquet"
EVENTS = paths.DERIVED / "events.parquet"
CASE_SCHEMA = pyarrow.schema(
    [
        ("court", pyarrow.string()),
        ("senate", pyarrow.int16()),
        ("number", pyarrow.int32()),
        ("year", pyarrow.int16()),
        ("filing_date", pyarrow.date32()),  # the first `ZAHAJ_RIZ` that isn't cancelled
        ("status", pyarrow.string()),  # `stav`, as given
        ("status_date", pyarrow.date32()),  # `stavDatum`
        ("valid_to", pyarrow.date32()),  # `platneK`: the record is complete up to this day
        ("linked", pyarrow.int16()),  # the number of `navazneVeci`, e.g. an appeal at the regional court
        ("weight", pyarrow.float64()),  # the senate-year's count / the cases sampled from it
        ("source", pyarrow.string()),  # "probe" (asked by step 4's hole probes) or "sample"
    ]
)
EVENT_SCHEMA = pyarrow.schema(
    [
        ("court", pyarrow.string()),
        ("senate", pyarrow.int16()),
        ("number", pyarrow.int32()),
        ("year", pyarrow.int16()),
        ("code", pyarrow.string()),  # `udalost`, e.g. ZAHAJ_RIZ (see reference/events.csv)
        ("date", pyarrow.date32()),
        ("poradi", pyarrow.int16()),  # the order of events on the same day
        ("cancelled", pyarrow.bool_()),  # `zruseno`
    ]
)


def allocation(counts, total=PER_COURT_YEAR):
    """{senate: cases to sample} for one court-year, from {senate: cases registered}: `total` split in
    proportion to the counts by largest remainders, then at least 1 each and at most the count."""
    whole = sum(counts.values())
    shares = {senate: total * count / whole for senate, count in counts.items()}
    wanted = {senate: int(share) for senate, share in shares.items()}
    extra = round(total - sum(wanted.values()))
    for senate in sorted(shares, key=lambda s: (wanted[s] - shares[s], s))[:extra]:
        wanted[senate] += 1
    return {senate: min(max(n, 1), counts[senate]) for senate, n in wanted.items()}


def order(court, senate, year, count):
    """A senate-year's numbers in the order they're tried: intake's probes, then the rest, shuffled."""
    first = intake.probe_numbers(count, f"{court}-{senate}-{year}")
    rest = sorted(set(range(1, count + 1)) - set(first))
    random.Random(f"sample-{court}-{senate}-{year}").shuffle(rest)
    return first + rest


def draw(find, court, senate, year, count, wanted):
    """One senate-year's sample: try its numbers in order until `wanted` cases are found, and never fewer
    than the probes. `find(number)` gives the case's record, or None if infosoud hides the number.
    Returns ([(number, record, source)], hidden numbers, numbers whose lookups kept failing or gave
    another case's record)."""
    numbers = order(court, senate, year, count)
    probes = set(intake.probe_numbers(count, f"{court}-{senate}-{year}"))
    wanted = max(wanted, len(probes))
    found, hidden, failed = [], 0, []
    for number in numbers:
        if len(found) >= wanted:
            break
        try:
            case = find(number)
        except (infosoud.LookupFailed, infosoud.WrongCase):
            failed.append(number)
            continue
        if case is None:
            hidden += 1
        else:
            found.append((number, case, "probe" if number in probes else "sample"))
    return found, hidden, failed


def targets(path=intake.PATH, total=PER_COURT_YEAR):
    """[(court, senate, year, count, wanted)] for every senate-year with cases, from intake.csv."""
    with open(path, encoding="utf-8", newline="") as file:
        rows = [row for row in csv.DictReader(file) if row["count"] and int(row["count"]) > 0]
    court_years = defaultdict(dict)
    for row in rows:
        court_years[row["court"], int(row["year"])][int(row["senate"])] = int(row["count"])
    out = []
    for (court, year), counts in sorted(court_years.items()):
        for senate, wanted in sorted(allocation(counts, total).items()):
            out.append((court, senate, year, counts[senate], wanted))
    return out


def case_row(court, senate, year, number, case, weight, source):
    filed = next(
        (
            e["datum"]
            for e in infosoud.sorted_events(case)
            if e["udalost"] == "ZAHAJ_RIZ" and not e["zruseno"]
        ),
        None,
    )
    return {
        "court": court,
        "senate": senate,
        "number": number,
        "year": year,
        "filing_date": _date(filed),
        "status": case.get("stav"),
        "status_date": _czech_date(case.get("stavDatum")),
        "valid_to": _date(case.get("platneK")),
        "linked": len(case.get("navazneVeci") or []),
        "weight": weight,
        "source": source,
    }


def event_rows(court, senate, year, number, case):
    return [
        {
            "court": court,
            "senate": senate,
            "number": number,
            "year": year,
            "code": event["udalost"],
            "date": _date(event["datum"]),
            "poradi": event["poradi"],
            "cancelled": bool(event["zruseno"]),
        }
        for event in infosoud.sorted_events(case)
    ]


def _date(text):
    try:
        return date.fromisoformat(text[:10])
    except (TypeError, ValueError):
        return None


def _czech_date(text):
    """ "19.10.2026" -> date(2026, 10, 19)."""
    try:
        day, month, year = (int(part) for part in text.split("."))
        return date(year, month, day)
    except (AttributeError, TypeError, ValueError):
        return None


def sample_all(client, todo, courts, log=None, keep=True):
    """Draw every senate-year's sample through `client`: the cases' rows, their events' rows (unless
    `keep` is false, as while fetching), and a tally of what happened."""
    cases, events, tally = [], [], Counter()
    for i, (court, senate, year, count, wanted) in enumerate(todo, 1):
        regional = courts[court]["regional_code"]

        def find(number, court=court, senate=senate, year=year, regional=regional):
            return infosoud.find_case(client, regional, court, "C", senate, number, year)

        found, hidden, failed = draw(find, court, senate, year, count, wanted)
        tally["hidden"] += hidden
        tally["failed"] += len(failed)
        tally["short"] += len(found) < wanted  # its numbers ran out, hidden or failing ones aside
        weight = count / len(found) if found else None
        for number, case, source in found:
            tally[source] += 1
            if keep:
                cases.append(case_row(court, senate, year, number, case, weight, source))
                events.extend(event_rows(court, senate, year, number, case))
        if log and (i % 100 == 0 or i == len(todo)):
            log.info(
                f"{i:,} of {len(todo):,} senate-years; {tally['probe'] + tally['sample']:,} cases; "
                f"{client.requests:,} requests; {tally['hidden']:,} hidden"
            )
    return cases, events, tally


def write(rows, schema, path):
    columns = {name: [row[name] for row in rows] for name in schema.names}
    table = pyarrow.Table.from_pydict(columns, schema=schema)
    path.parent.mkdir(parents=True, exist_ok=True)
    pyarrow.parquet.write_table(table, path, compression="zstd")


def run(parse_only=False):
    courts = {court["code"]: court for court in reference.courts()}
    todo = targets()
    if not parse_only:
        with Client("sample") as client:
            infosoud.backend_version(client)
            wanted = sum(t[4] for t in todo)
            client.log.info(f"{len(todo):,} senate-years, {wanted:,} cases wanted (probes counted in)")
            sample_all(client, todo, courts, log=client.log, keep=False)
    with CacheReader() as cache:
        cases, events, tally = sample_all(cache, todo, courts)
    write(cases, CASE_SCHEMA, CASES)
    write(events, EVENT_SCHEMA, EVENTS)
    print("\n".join(summary(cases, events, tally)))
    return 0


def summary(cases, events, tally):
    by_year = Counter(row["year"] for row in cases)
    weights = defaultdict(float)
    for row in cases:
        weights[row["year"]] += row["weight"]
    return [
        f"{len(cases):,} cases sampled ({tally['probe']:,} from step 4's probes), "
        f"with {len(events):,} events",
        "By year: " + ", ".join(f"{year}: {n:,}" for year, n in sorted(by_year.items())),
        "Weights add up to: " + ", ".join(f"{year}: {w:,.0f}" for year, w in sorted(weights.items())),
        f"Hidden numbers skipped: {tally['hidden']:,}; "
        f"lookups that kept failing or gave another case: {tally['failed']:,}",
        f"Senate-years short of their target: {tally['short']:,}",
    ]
