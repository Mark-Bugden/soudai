"""Event codes and case statuses: reference/events.csv. The event log and the stage model join this
module in milestones 5 and 6.

The table has a row for each event code infosoud's app labels for the district, regional and high
courts, and a row for each case status the API has been seen to return. The Czech labels, tooltips
and descriptions come from the app's JS bundle, and the English glosses are written by hand. The
bundle has no labels for statuses: their codes are the API's `stav` strings, added by hand.

    uv run soudai events   # refresh the Czech labels from the current bundle, keeping the glosses
"""

from datetime import date

from . import infosoud, paths, reference
from .http import Client

COLUMNS = ["kind", "code", "label_cs", "tooltip_cs", "description_cs", "gloss_en"]


def merge(labels, existing):
    """The table's rows: the bundle's event labels with the glosses already written, then the statuses."""
    glosses = {row["code"]: row["gloss_en"] for row in existing if row["kind"] == "event"}
    rows = [
        {
            "kind": "event",
            "code": code,
            "label_cs": label["label"],
            "tooltip_cs": label["tooltip"],
            "description_cs": label["description"],
            "gloss_en": glosses.get(code, ""),
        }
        for code, label in sorted(labels.items())
    ]
    return rows + [row for row in existing if row["kind"] == "status"]


def run():
    with Client("events") as client:
        backend = infosoud.backend_version(client)
        chunk_name, chunk = infosoud.labels_chunk(client)
    labels = infosoud.event_labels(chunk)
    path = paths.REFERENCE / "events.csv"
    existing = reference.events() if path.exists() else []
    gone = sorted({row["code"] for row in existing if row["kind"] == "event"} - labels.keys())
    rows = merge(labels, existing)
    reference.write_csv("events.csv", rows, COLUMNS)
    reference.update_sources(
        {
            "infosoud": {
                "backend_version": backend,
                "labels_chunk": chunk_name,
                "checked": date.today().isoformat(),
            }
        }
    )
    unglossed = [row["code"] for row in rows if not row["gloss_en"]]
    print(f"Wrote {len(labels)} event codes from {chunk_name} to {path}")
    if gone:
        print(f"No longer in the bundle, and dropped: {', '.join(gone)}")
    if unglossed:
        print(f"Still to gloss in English: {', '.join(unglossed)}")
    return 0
