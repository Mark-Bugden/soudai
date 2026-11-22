"""The district-level courts in scope: reference/courts.csv.

Built from infosoud's court lists, with the names rozhodnuti uses taken from the old project's court
map (SOUDAI_data_scraping's references/court_map.yaml, at a fixed commit), and checked by hand.
reference/README.md describes the table and the checks.

    uv run soudai courts           # compare infosoud's lists with reference/courts.csv
    uv run soudai courts --write   # write reference/courts.csv afresh
"""

import re
from datetime import date

from . import infosoud, paths, reference
from .http import Client

SEED_COMMIT = "a9f5ba3751e25926fc014166efaee870e33973e8"
SEED_URL = f"https://raw.githubusercontent.com/Mark-Bugden/SOUDAI_data_scraping/{SEED_COMMIT}/references/court_map.yaml"
COLUMNS = ["code", "regional_code", "name", "rozhodnuti_names", "area"]

# Courts named after a city whose okres has a different name.
AREAS = {"Městský soud Brno": "Brno-město", "Okresní soud Ostrava": "Ostrava-město"}


def area(name):
    """The area a court serves, as named: its okres, or for Prague's district courts, the Prague district."""
    if name in AREAS:
        return AREAS[name]
    place = name.removeprefix("Okresní soud ").removeprefix("Obvodní soud ")
    # infosoud capitalises three okres names that are officially lower case after the hyphen.
    head, hyphen, tail = place.partition("-")
    return f"{head}-{tail.lower()}" if tail in ("Město", "Východ", "Západ") else place


def parse_seed(text):
    """The old court map's district courts: {infosoud code: [the names rozhodnuti uses]}.

    A court with branches has several names, e.g. "Okresní soud v Bruntále, pobočka Krnov".
    """
    names = {}
    for block in re.split(r"\n(?=- name:)", text):
        name = re.search(r'^- name: "([^"]+)"', block, re.MULTILINE)
        code = re.search(r'^\s+Org: "(\w+)"', block, re.MULTILINE)
        if name and code:
            names.setdefault(code.group(1), []).append(name.group(1))
    return names


def build(client):
    """One row per district-level court, in order of code."""
    seed = parse_seed(client.get(SEED_URL).text)
    rows = []
    for regional in infosoud.regional_courts(client):
        for court in infosoud.district_courts(client, regional["kod"]):
            names = seed.get(court["kod"])
            if not names:
                raise ValueError(
                    f"the court map has no rozhodnuti name for {court['kod']} ({court['nazev']})"
                )
            rows.append(
                {
                    "code": court["kod"],
                    "regional_code": regional["kod"],
                    "name": court["nazev"],
                    "rozhodnuti_names": "; ".join(names),
                    "area": area(court["nazev"]),
                }
            )
    return sorted(rows, key=lambda row: row["code"])


def compare(old, new):
    """The differences between two versions of the table, as lines of text."""
    old, new = {row["code"]: row for row in old}, {row["code"]: row for row in new}
    lines = [f"new: {code} {new[code]['name']}" for code in sorted(new.keys() - old.keys())]
    lines += [f"gone: {code} {old[code]['name']}" for code in sorted(old.keys() - new.keys())]
    for code in sorted(old.keys() & new.keys()):
        for column in COLUMNS:
            if old[code][column] != new[code][column]:
                lines.append(f"changed: {code} {column}: {old[code][column]!r} -> {new[code][column]!r}")
    return lines


def run(write=False):
    with Client("courts") as client:
        backend = infosoud.backend_version(client)
        rows = build(client)
    path = paths.REFERENCE / "courts.csv"
    if write or not path.exists():
        reference.write_csv("courts.csv", rows, COLUMNS)
        reference.update_sources(
            {
                "infosoud": {"backend_version": backend, "checked": date.today().isoformat()},
                "court_map": {"url": SEED_URL, "commit": SEED_COMMIT},
            }
        )
        print(f"Wrote {len(rows)} courts to {path}")
        return 0
    differences = compare(reference.courts(), rows)
    for line in differences:
        print(line)
    print(f"{len(rows)} courts on infosoud; {len(differences) or 'no'} differences from {path.name}")
    return 1 if differences else 0
