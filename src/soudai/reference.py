"""Reading and writing the hand-checked tables in reference/, and its record of sources."""

import csv
import json

from . import paths


def read_csv(name, folder=paths.REFERENCE):
    with open(folder / name, encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(name, rows, columns, folder=paths.REFERENCE):
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / name, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def courts():
    return read_csv("courts.csv")


def events():
    return read_csv("events.csv")


def update_sources(updates, folder=paths.REFERENCE):
    """Merge `updates` into sources.json, one level of nesting deep (e.g. {"infosoud": {"checked": ...}})."""
    path = folder / "sources.json"
    sources = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(sources.get(key), dict):
            sources[key] |= value
        else:
            sources[key] = value
    path.write_text(json.dumps(sources, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
