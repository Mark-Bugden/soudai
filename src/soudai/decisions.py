"""Published decisions (milestone 3): everything rozhodnuti has published since 2020, listed day by day
and parsed to data/derived/decisions.parquet.

    uv run soudai decisions                       # list up to yesterday, then parse
    uv run soudai decisions --until 2020-12-31    # list and parse up to a given day
    uv run soudai decisions --parse-only          # parse what's cached, fetching nothing

A listing of a period (a year's months, a month's days, a day's page) is trusted from the cache only if
it was fetched after the period ended. Otherwise it's fetched again, so a rerun picks up what was
published since. Parsing keeps the case number, the court, the dates and the subject (`predmetRizeni`).
It drops the judge's name (`autor`), the keywords, the statutes cited and the link to the full text.
"""

import calendar
import re
from collections import Counter
from datetime import date, timedelta
from itertools import pairwise

import pyarrow
import pyarrow.parquet

from . import paths, reference, rozhodnuti
from .http import CacheReader, Client, with_params

FIRST_YEAR = 2020
PATH = paths.DERIVED / "decisions.parquet"
SCHEMA = pyarrow.schema(
    [
        ("court", pyarrow.string()),  # infosoud's code, for a district-level court; else null
        ("court_name", pyarrow.string()),  # rozhodnuti's `soud`, as given
        ("case_number", pyarrow.string()),  # `jednaciCislo`, as given
        ("senate", pyarrow.int16()),  # the case number's parts, or null if it doesn't parse
        ("register", pyarrow.string()),
        ("number", pyarrow.int32()),
        ("year", pyarrow.int16()),
        ("document", pyarrow.int32()),  # null for a case number without one
        ("decision_date", pyarrow.date32()),  # `datumVydani`
        ("publication_date", pyarrow.date32()),  # `datumZverejneni`
        ("subject", pyarrow.string()),  # `predmetRizeni`
    ]
)
SORT = ["publication_date", "court_name", "year", "senate", "register", "number", "document", "case_number"]


def stale(client, url, period_end):
    """Whether a cached listing was fetched before its period ended, and so may be missing some of it."""
    response = client.cached("GET", url)
    return response is not None and response.fetched_at[:10] <= period_end.isoformat()


def listing(client, until):
    """[(day, decisions published that day)] for every day from 2020 to `until` that has any."""
    days = []
    for year in sorted(rozhodnuti.years(client, refresh=True)):
        if not FIRST_YEAR <= year <= until.year:
            continue
        refresh = stale(client, f"{rozhodnuti.API}/{year}", date(year, 12, 31))
        for month in sorted(rozhodnuti.months(client, year, refresh=refresh)):
            if date(year, month, 1) > until:
                continue
            end = date(year, month, calendar.monthrange(year, month)[1])
            refresh = stale(client, f"{rozhodnuti.API}/{year}/{month}", end)
            for day, count in sorted(rozhodnuti.days(client, year, month, refresh=refresh).items()):
                if day <= until:
                    days.append((day, count))
    return days


def day_items(client, day):
    """(the day's totalElements, every item on its pages). Page 0 says how many pages there are."""
    first = _page(client, day, 0)
    items = list(first["items"])
    for page in range(1, first["totalPages"]):
        items += _page(client, day, page)["items"]
    return first["totalElements"], items


def _page(client, day, page):
    url = with_params(f"{rozhodnuti.API}/{day.year}/{day.month}/{day.day}", {"page": page})
    return rozhodnuti.day_page(client, day, page, refresh=stale(client, url, day))


def parse(client, days, courts):
    """The decisions table's columns, the judges' names seen (to check none survive), and the days whose
    index count, totalElements and items disagree."""
    names = {name: court["code"] for court in courts for name in court["rozhodnuti_names"].split("; ")}
    columns = {name: [] for name in SCHEMA.names}
    judges, disagreements = set(), []
    for day, count in days:
        total, items = day_items(client, day)
        if not count == total == len(items):
            disagreements.append((day, count, total, len(items)))
        for item in items:
            judges.add(item.get("autor"))
            for name, value in row(item, names).items():
                columns[name].append(value)
    judges.discard(None)
    return columns, judges, disagreements


def row(item, names):
    """One decision's row. Only the fields named here are kept."""
    number = (item.get("jednaciCislo") or "").strip()
    senate, register, case, year, document = rozhodnuti.parse_case_number(number) or (None,) * 5
    return {
        "court": names.get(item.get("soud")),
        "court_name": item.get("soud"),
        "case_number": number,
        "senate": senate,
        "register": register,
        "number": case,
        "year": year,
        "document": document,
        "decision_date": _date(item.get("datumVydani")),
        "publication_date": _date(item.get("datumZverejneni")),
        "subject": item.get("predmetRizeni"),
    }


def _date(text):
    try:
        return date.fromisoformat(text[:10])
    except (TypeError, ValueError):
        return None


# JUDr., Ph.D., LL.M. and so on, and the words for a judge's role that sometimes follow the name.
TITLE = re.compile(r"^(?:[\w.]*\.[\w.]*|MBA|DiS|CSc|DrSc|Dr|Mgr|Bc|Ing|et)$", re.IGNORECASE)
ROLES = {"předseda", "předsedkyně", "senátu", "soudce", "soudkyně", "samosoudce", "samosoudkyně", "asistent"}
# `autor` values that are places, not judges, each checked by hand: five decisions from 2020 to
# 2026-11-20. They're in court names and subjects, so the check leaves them out.
NOT_JUDGES = {"Hradci Králové", "Karlovy Vary", "Nový Jičín", "Valašském Meziříčí"}


def name_pairs(autor):
    """The pairs of adjacent words in an `autor` field, without titles or roles, each capitalised:
    "JUDr. Jan Novák, Ph.D." gives {"Jan Novák"}. The field sometimes holds more than one name, a
    number, or a name in lower case, and a pair still catches each name."""
    words = [
        word[:1].upper() + word[1:]
        for word in re.split(r"[\s,;]+", autor)
        if word.replace("-", "").isalpha() and not TITLE.match(word) and word.lower() not in ROLES
    ]
    return {f"{first} {second}" for first, second in pairwise(words)}


def judges_in(columns, judges):
    """The judges' names that appear in a text column of the table. There should be none."""
    text = "\n".join({value for name in ("court_name", "subject") for value in columns[name] if value})
    names = {pair for judge in judges if judge.strip() not in NOT_JUDGES for pair in name_pairs(judge)}
    return sorted(name for name in names if len(name) >= 6 and name in text)


def write(columns, until, path=PATH):
    table = pyarrow.Table.from_pydict(columns, schema=SCHEMA)
    table = table.sort_by([(name, "ascending", "at_end") for name in SORT])
    table = table.replace_schema_metadata({"snapshot": until.isoformat(), "source": rozhodnuti.API})
    path.parent.mkdir(parents=True, exist_ok=True)
    pyarrow.parquet.write_table(table, path, compression="zstd")
    return table


LEVELS = [
    ("regional", ("Krajský soud", "Městský soud v Praze")),
    ("high", ("Vrchní soud",)),
    ("supreme", ("Nejvyšší",)),
    ("not given", ("(nezadán)",)),
]
DISTRICT_LIKE = ("Okresní soud", "Obvodní soud", "Městský soud v Brně")


def level(court_name, court):
    if court:
        return "district"
    for name, prefixes in LEVELS:
        if (court_name or "").startswith(prefixes):
            return name
    return "other"


def summary(columns, disagreements, judges_found, path=PATH):
    """What the plan records about the run, as lines of text."""
    courts = list(zip(columns["court_name"], columns["court"], strict=True))
    levels = Counter(level(name, court) for name, court in courts)
    registers = Counter(r for r, (_, court) in zip(columns["register"], courts, strict=True) if court)
    numbers = zip(columns["case_number"], columns["senate"], strict=True)
    unparsed = [number for number, senate in numbers if senate is None]
    unmapped = Counter(name for name, court in courts if not court and (name or "").startswith(DISTRICT_LIKE))
    others = Counter(name for name, court in courts if level(name, court) == "other")
    repeated = Counter(zip(columns["court_name"], columns["case_number"], strict=True))
    years = Counter(day.year for day in columns["publication_date"] if day)
    size = path.stat().st_size / 1e6
    return [
        f"{len(courts):,} decisions published from {FIRST_YEAR} to the snapshot, {size:.1f} MB at {path}",
        "By year of publication: " + ", ".join(f"{year}: {n:,}" for year, n in sorted(years.items())),
        "By court level: " + ", ".join(f"{name}: {n:,}" for name, n in levels.most_common()),
        "Registers at district-level courts: "
        + ", ".join(f"{r}: {n:,}" for r, n in registers.most_common(12)),
        f"Case numbers that don't parse: {len(unparsed):,}"
        + (f", e.g. {', '.join(repr(u) for u in unparsed[:8])}" if unparsed else ""),
        f"District-like court names that don't map to a court: {dict(unmapped) or 'none'}",
        f"Courts of no known level: {dict(others.most_common(10)) or 'none'}",
        f"Court and case number pairs listed more than once: {sum(1 for n in repeated.values() if n > 1):,}",
        f"Days whose index count, totalElements and items disagree: {len(disagreements):,}"
        + (f", e.g. {disagreements[:5]}" if disagreements else ""),
        f"Judges' names found in the table: {len(judges_found)}",
    ]


def run(until=None, parse_only=False):
    until = until or date.today() - timedelta(days=1)
    if not parse_only:
        with Client("decisions") as client:
            days = listing(client, until)
            total = sum(count for _, count in days)
            client.log.info(f"{len(days):,} days with {total:,} decisions from {FIRST_YEAR} to {until}")
            for i, (day, _) in enumerate(days, 1):
                day_items(client, day)
                if i % 20 == 0 or i == len(days):
                    client.log.info(f"{i:,} of {len(days):,} days, up to {day}; {client.requests:,} requests")
    with CacheReader() as cache:
        columns, judges, disagreements = parse(cache, listing(cache, until), reference.courts())
    judges_found = judges_in(columns, judges)
    if judges_found:
        raise ValueError(f"judges' names in the decisions table, which isn't written: {judges_found[:5]}")
    write(columns, until)
    print("\n".join(summary(columns, disagreements, judges_found)))
    return 0
