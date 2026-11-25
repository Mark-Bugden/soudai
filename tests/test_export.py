"""Checks on the demo's data file, demo/public/data/soudai.json (milestone 8), which is committed: it matches
the derived tables it's built from, stays under its size budget, holds no free text, and its network gives
the full network's forecasts."""

import json
import re
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from soudai import events, export, forward, journey, model, paths, reference


@pytest.fixture(scope="module")
def data():
    return json.loads(paths.EXPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def weights():
    return json.loads(model.NETWORK.read_text(encoding="utf-8"))


def test_size():
    assert paths.EXPORT.stat().st_size < export.MAX_BYTES


def test_it_is_up_to_date_with_the_derived_tables(data):
    """`uv run soudai export` would write the same file."""
    rebuilt = export.dumps(
        export.build(
            json.loads(model.NETWORK.read_text(encoding="utf-8")),
            *journey.load(),
            pd.read_csv(model.DEMO_CASES),
            pd.read_csv(model.SCORES),
            pd.read_csv(model.CALIBRATION),
            {name: pd.read_csv(path) for name, path in journey.OUT.items()},
            pd.read_csv(paths.DERIVED / "intake.csv"),
        )
    )
    assert rebuilt == paths.EXPORT.read_text(encoding="utf-8")


@pytest.mark.parametrize("shape", [(3, 4), (7,), (2, 2)])
def test_weights_round_trip_to_within_half_a_step(shape):
    values = np.random.default_rng(0).normal(0, 2, shape)
    encoded = export.encode(values)
    assert encoded["shape"] == list(shape)
    back = export.decode(encoded)
    assert back.shape == shape
    assert np.abs(back - values).max() <= encoded["scale"] / 2 + 1e-12
    assert np.abs(back).max() == pytest.approx(np.abs(values).max())


def test_zero_weights_round_trip():
    assert (export.decode(export.encode(np.zeros((2, 3)))) == 0).all()


def test_the_exported_network_gives_the_full_networks_forecasts(data, weights):
    """On the first 40 real cases, at filing and on each day with events before the end."""
    exported = export.decoded(data["network"], weights)
    courts, codes = [c["code"] for c in data["courts"]], [c["code"] for c in data["codes"]]
    gap = 0.0
    for court, *_, span, _, pairs in data["cases"]["rows"][:40]:
        history = [(codes[pairs[i]], pairs[i + 1]) for i in range(0, len(pairs), 2)]
        for day in sorted({day for _, day in history if day < span}):
            so_far = [event for event in history if event[1] <= day]
            full = forward.still_open(weights, courts[court], so_far, day)
            gap = max(gap, np.abs(forward.still_open(exported, courts[court], so_far, day) - full).max())
    assert gap < 1e-4


def test_courts_and_codes_are_in_the_networks_order(data, weights):
    assert [c["code"] for c in data["courts"]] == weights["courts"]
    assert [c["code"] for c in data["codes"]] == weights["codes"]
    assert {c["code"] for c in data["courts"]} == {row["code"] for row in reference.courts()}
    assert all(c["gloss"] for c in data["codes"])
    assert {c["stage"] for c in data["codes"]} == set(events.STAGES) | {None}


def test_the_real_cases(data):
    rows = data["cases"]["rows"]
    assert data["cases"]["columns"] == [
        "court",
        "senate",
        "number",
        "year",
        "filed",
        "span",
        "ended",
        "events",
    ]
    assert len(rows) == len(pd.read_csv(model.DEMO_CASES))
    codes = [c["code"] for c in data["codes"]]
    per_court = np.bincount([row[0] for row in rows], minlength=len(data["courts"]))
    assert (per_court == 35).all()
    for court, senate, number, year, filed, span, ended, pairs in rows:
        history = [(codes[pairs[i]], pairs[i + 1]) for i in range(0, len(pairs), 2)]
        days = [day for _, day in history]
        assert history[0] == ("ZAHAJ_RIZ", 0)
        assert days == sorted(days) and days[-1] <= span
        assert 2024 <= year <= 2025 and ended in (0, 1)
        assert date.fromisoformat(data["split"]) + timedelta(days=filed) <= date(year, 12, 31)
        ending = {code for code, day in history if day == span}
        if ended:
            assert ending & {events.FINAL, events.CLOSED}, (court, senate, number, year)
        assert events.FINAL not in {code for code, day in history if day < span}


def test_the_journey_covers_every_court(data):
    journeys = data["journey"]
    assert set(journeys) == {"all"} | {c["code"] for c in data["courts"]}
    assert journeys["all"]["registered"] == data["registered"]
    assert sum(j["registered"] for scope, j in journeys.items() if scope != "all") == data["registered"]
    for scope, j in journeys.items():
        assert len(j["stages"]) == len(events.STAGES) and j["stages"][0] == 1
        assert len(j["notDecided"]) == len(j["notFinal"]) == journey.MONTHS + 1
        assert all(a >= b for a, b in zip(j["notFinal"], j["notFinal"][1:], strict=False)), scope
        for start, end, share, sampled, *waits in j["moves"]:
            assert 0 <= start < len(events.STAGES) - 1 and 0 <= end < len(data["stages"])
            assert 0 <= share <= 1 and sampled > 0
            assert (None in waits) == (sampled < journey.MIN_MOVES)
        for path, ending, share, sampled in j["paths"]:
            assert path[0] == 0 and ending in data["endings"] and 0 < share <= 1 and sampled > 0


def test_the_scores(data):
    columns = data["scores"]["columns"]
    rows = {(row[0], row[1], row[2]): dict(zip(columns, row, strict=True)) for row in data["scores"]["rows"]}
    models = {model for model, _, _ in rows}
    assert "gru ensemble" in models and "gru" not in models
    table = pd.read_csv(model.SCORES).set_index(["model", "court", "landmark"])
    ensemble = rows[("gru ensemble", "all", "all")]
    assert ensemble["concordance"] == pytest.approx(
        table.loc[("gru ensemble", "all", "all"), "concordance"], abs=1e-4
    )
    calibration = pd.DataFrame(data["calibration"]["rows"], columns=data["calibration"]["columns"])
    assert calibration.groupby(["model", "horizon"])["share"].sum().round(3).eq(1).all()


DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BASE64 = re.compile(r"^[A-Za-z0-9+/]+=*$")


def _strings(value, path=()):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield path + (key,), key
            yield from _strings(item, path + (key,))
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item, path)


def test_it_holds_no_free_text(data):
    """Every string is a court's name or area, an event's code or gloss, a name the export gives, a date or
    the network's weights. So no name of a judge, party or anyone else can be in it."""
    allowed = {c[k] for c in data["courts"] for k in ("code", "name", "area")}
    allowed |= {c[k] for c in data["codes"] for k in ("code", "gloss") if c[k]}
    allowed |= set(data["stages"]) | set(data["endings"]) | {"all"}
    allowed |= {row[0] for row in data["scores"]["rows"]} | set(export.METRICS)
    allowed |= (
        set(data["scores"]["columns"]) | set(data["calibration"]["columns"]) | set(data["cases"]["columns"])
    )
    allowed |= set(data) | {"code", "name", "area", "gloss", "stage", "columns", "rows", "horizon", "members"}
    allowed |= {"shape", "scale", "values"} | set(data["network"]["members"][0])
    allowed |= set(data["journey"]["all"]) | {str(m) for m in [0, 1, 3, 6, 12]}
    for path, string in _strings(data):
        if path[-1:] == ("values",):
            assert BASE64.match(string)
        else:
            assert string in allowed or DATE.match(string), (path, string)
