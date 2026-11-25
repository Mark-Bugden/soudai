"""Event codes and case statuses (reference/events.csv), and the stage model of the journey map.

The table has a row for each event code infosoud's app labels for the district, regional and high
courts, and a row for each case status the API has been seen to return. The Czech labels, tooltips
and descriptions come from the app's JS bundle, and the English glosses are written by hand. The
bundle has no labels for statuses: their codes are the API's `stav` strings, added by hand.

The stage model was settled with Mark on 2026-11-25 (docs/plan.md, "The journey"). It reads the event
log, data/derived/events.parquet, from step 5.

    uv run soudai events   # refresh the Czech labels from the current bundle, keeping the glosses
"""

from datetime import date

from . import infosoud, paths, reference
from .http import Client

COLUMNS = ["kind", "code", "label_cs", "tooltip_cs", "description_cs", "gloss_en"]
CASE = ["court", "senate", "number", "year"]

# The stages of the journey map, and the events that put a case in each. Cancelled events, "proceedings
# resumed" (ST_VEC_UPR, which only ends a suspension), "closed in the register" (ST_VEC_ODS) and the
# codes the sample never uses aren't on the map. "appeal" is any challenge to a decision, at a higher
# court or at the district court itself, and a higher court's ruling on a side question.
STAGES = ["filed", "hearing", "decided", "appeal", "revived", "suspended", "final"]
STAGE = {
    "ZAHAJ_RIZ": "filed",
    "NAR_JED": "hearing",  # dated the day the hearing is held
    "VYD_ROZH": "decided",
    "ST_VEC_VYR": "decided",  # the same day as the decision in 96% of cases
    "POD_OP_PR": "appeal",
    "ODES_SPIS": "appeal",
    "ODVOLANI": "appeal",  # at the appeal court, as a linked case
    "NAD_RIZENI": "appeal",
    "DOVOL_RIZ": "appeal",
    "VYR_OP_PR": "appeal",
    "VRAC_SPIS": "appeal",
    "ST_VEC_OBZ": "revived",
    "ST_VEC_PRE": "suspended",
    "ST_VEC_PUK": "final",
}
FINAL, CLOSED, DISPOSED, REVIVED = "ST_VEC_PUK", "ST_VEC_ODS", "ST_VEC_VYR", "ST_VEC_OBZ"


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


def log(cases, events):
    """The events the journey reads, in order: those not cancelled, dated on or after the case's filing
    (its first filing event) and no later than the day its record runs to (`valid_to`), sorted by date,
    then `poradi`, with the filing first on its day. So an event dated before the filing is left off, and
    so is one that hasn't happened yet, such as a hearing booked ahead. A case with no filing is left out."""
    events = events[~events["cancelled"]]
    filed = events[events["code"] == "ZAHAJ_RIZ"].groupby(CASE)["date"].min().rename("filed")
    events = events.join(filed, on=CASE, how="inner").join(cases.set_index(CASE)["valid_to"], on=CASE)
    events = events[(events["date"] >= events["filed"]) & (events["date"] <= events["valid_to"])]
    events = events.assign(later=events["code"] != "ZAHAJ_RIZ")
    events = events.sort_values(CASE + ["date", "later", "poradi"], kind="stable")
    return events.drop(columns=["filed", "valid_to", "later"]).reset_index(drop=True)


def journey(cases, events):
    """Each case's path through the stages: one row per visit, in order, with the case, the stage, the
    day the case entered it (`date`) and how many events the visit holds (`events`). A visit is a run of
    events in one stage, so repeated hearings are one visit. The path starts at the filing and stops at
    the first "legally final": later events, such as an appeal about costs, are left off."""
    events = log(cases, events)
    events = events[events["code"].isin(STAGE)]
    events = events.assign(stage=events["code"].map(STAGE))
    final = (events["stage"] == "final").astype(int)
    events = events[final.groupby([events[c] for c in CASE]).cumsum() - final == 0]
    new = events["stage"].ne(events.groupby(CASE)["stage"].shift()).astype(int)
    events = events.assign(visit=new.groupby([events[c] for c in CASE]).cumsum())
    visits = events.groupby(CASE + ["visit"], sort=False).agg(
        stage=("stage", "first"), date=("date", "first"), events=("code", "size")
    )
    return visits.reset_index()


def outcomes(cases, events):
    """Each case's dates for the curves and the model, one row per case with a filing:
    - `filed`: its first filing;
    - `end` and `how`: when it finished, and how. That's its first "legally final" ("final"), or for a
      case closed in the register without one, its first closing ("closed"). None while it's open;
    - `disposed`: its latest disposal (infosoud keeps only a case's latest disposal date), or None if it
      has none or was revived after it and is still open. It's never later than the case's end, and a
      case that finished without a disposal date counts as disposed when it finished;
    - `until`: its end, or for an open case the day its record runs to (`valid_to`), where it's censored.
    """
    events = log(cases, events)

    def first(code):
        return events[events["code"] == code].groupby(CASE)["date"].first()

    out = cases.set_index(CASE)[["valid_to"]].join(first("ZAHAJ_RIZ").rename("filed"), how="inner")
    final, closed = first(FINAL), first(CLOSED)
    out["end"] = final.reindex(out.index).combine_first(closed.reindex(out.index))
    out["how"] = None
    out.loc[out.index.isin(closed.index), "how"] = "closed"
    out.loc[out.index.isin(final.index), "how"] = "final"
    steps = events.reset_index()
    last = steps[steps["code"] == DISPOSED].groupby(CASE).agg(date=("date", "last"), step=("index", "last"))
    revived = steps[steps["code"] == REVIVED].groupby(CASE)["index"].last()
    reopened = (revived.reindex(out.index) > last["step"].reindex(out.index)) & out["end"].isna()
    disposed = last["date"].reindex(out.index).where(~reopened)
    out["disposed"] = disposed.where(~(disposed > out["end"]), out["end"]).combine_first(out["end"])
    out["until"] = out["end"].combine_first(out["valid_to"])
    out = out[["filed", "disposed", "end", "how", "until"]].astype(object)
    return out.where(out.notna(), None).reset_index()
