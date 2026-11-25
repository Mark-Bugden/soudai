"""The network: the numpy forward pass against PyTorch, the loss by hand, the batches, and learning.

tests/fixtures/network/forward.json holds a network with random weights and its PyTorch forecasts at every
cut of a few made-up cases, so the numpy forward pass (and later the demo's JavaScript) can be checked
without PyTorch. Rewrite it with `uv run --group model python tests/test_network.py`.
"""

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from soudai import examples, forward

FIXTURE = Path(__file__).parent / "fixtures" / "network" / "forward.json"
START = date(2023, 3, 1)


def case(number, court, steps, valid_to=date(2026, 11, 23)):
    key = {"court": court, "senate": 1, "number": number, "year": 2023}
    rows = [
        key | {"code": code, "date": START + timedelta(days=day), "poradi": i, "cancelled": False}
        for i, (code, day) in enumerate(steps, 1)
    ]
    return key | {"valid_to": valid_to, "weight": 1.0}, rows


MADE_UP = [
    case(
        1,
        "OSVYCNA",
        [("ZAHAJ_RIZ", 0), ("NAR_JED", 100), ("VYD_ROZH", 100), ("ST_VEC_VYR", 100), ("ST_VEC_PUK", 130)],
    ),
    case(
        2,
        "OSPHA01",
        [
            ("ZAHAJ_RIZ", 0),
            ("VYD_ROZH", 20),
            ("ST_VEC_VYR", 20),
            ("POD_OP_PR", 25),
            ("ODVOLANI", 40),
            ("ST_VEC_OBZ", 50),
            ("NAR_JED", 70),
            ("ST_VEC_PRE", 85),
            ("ST_VEC_UPR", 88),
            ("VYD_ROZH", 95),
            ("ST_VEC_VYR", 95),
            ("ST_VEC_PUK", 125),
        ],
    ),
    case(3, "OSJICCB", [("ZAHAJ_RIZ", 0), ("NAR_JED", 45)], valid_to=START + timedelta(days=200)),
]


def made_up_examples(made=MADE_UP):
    cases = pd.DataFrame([row for row, _ in made])
    table = pd.DataFrame([event for _, rows in made for event in rows])
    return examples.build(cases, table)


def make_fixture(seed=1):
    """A network with random weights, and its PyTorch forecasts at every cut of the made-up cases."""
    import torch

    from soudai import network

    torch.manual_seed(seed)
    model = network.Network()
    built = made_up_examples()
    still = network.still_open(model, network.Data(built, built.cuts))
    steps = built.steps
    forecasts = []
    for i, cut in enumerate(built.cuts.itertuples()):
        so_far = steps[(steps["id"] == cut.id) & (steps.index <= cut.step)]
        forecasts.append(
            {
                "court": cut.court,
                "events": [[code, int(day)] for code, day in zip(so_far["code"], so_far["day"], strict=True)],
                "day": int(cut.day),
                "still_open": [round(float(x), 12) for x in still[i]],
            }
        )
    return {"weights": network.weights(model), "forecasts": forecasts}


def test_the_numpy_forward_pass_matches_pytorch():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(fixture["forecasts"]) == 6 + 13 + 8  # the made-up cases' cuts
    for f in fixture["forecasts"]:
        still = forward.still_open(fixture["weights"], f["court"], f["events"], f["day"])
        assert still == pytest.approx(f["still_open"], abs=1e-6)  # PyTorch works in 32-bit floats


def test_the_fixture_is_up_to_date():
    pytest.importorskip("torch")
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fresh = make_fixture()
    assert fresh["weights"]["codes"] == fixture["weights"]["codes"]
    assert [f["events"] for f in fresh["forecasts"]] == [f["events"] for f in fixture["forecasts"]]
    for new, old in zip(fresh["forecasts"], fixture["forecasts"], strict=True):
        assert new["still_open"] == pytest.approx(old["still_open"], abs=1e-6)


def test_the_loss_by_hand():
    torch = pytest.importorskip("torch")
    from soudai import network

    # Two cuts with every month's chance of finishing 1/2: one finished in month 3, and one known to be
    # open after 2 months. The first is -[2 log(1/2) + log(1/2)], over 3 months; the second -2 log(1/2),
    # over 2.
    logits = torch.zeros((2, network.HORIZON))
    batch = {
        "finished": torch.tensor([3, 0]),
        "known": torch.tensor([2, 2]),
        "weight": torch.tensor([1.0, 3.0]),
    }
    loss, rows = network.loss_terms(logits, batch)
    assert loss.item() == pytest.approx((3 + 3 * 2) * np.log(2))
    assert rows.item() == 3 + 3 * 2


def test_a_batch_pads_cases_and_points_each_cut_at_its_last_event():
    pytest.importorskip("torch")
    from soudai import network

    built = made_up_examples()
    data = network.Data(built, built.cuts)
    batch, cuts = data.batch(np.arange(len(data.ids)))
    assert cuts.tolist() == list(range(len(built.cuts)))
    ids = built.histories.set_index("number")["id"]  # cases are in court order: 3, 2, 1
    assert batch["codes"].shape == (3, 11)  # case 2 has 11 events before its end
    assert batch["numbers"][ids[3], 2:].abs().sum() == 0  # case 3 has 2, and the rest is padding
    last = [network.CODES[c] for c in batch["codes"][batch["row"], batch["position"]].tolist()]
    assert last == built.steps["code"].to_numpy()[built.cuts["step"]].tolist()
    # case 1 finished on day 130: from day 0, in month 5 (day 121.8 to 152.2); from day 100, in month 1
    first = (built.cuts["id"] == ids[1]).to_numpy()
    assert batch["finished"][first].tolist() == [5, 4, 3, 2, 1, 1]
    # case 3 was censored on day 200: from day 91, open for 3 whole months; from day 183, for none
    third = (built.cuts["id"] == ids[3]).to_numpy()
    assert batch["finished"][third][-4:].tolist() == [0, 0, 0, 0]
    assert batch["known"][third][-4:].tolist() == [3, 2, 1, 0]


def test_forecasts_come_back_in_the_order_asked():
    torch = pytest.importorskip("torch")
    from soudai import network

    torch.manual_seed(1)
    model = network.Network()
    built = made_up_examples()
    ahead = network.still_open(model, network.Data(built, built.cuts))
    back = network.still_open(model, network.Data(built, built.cuts.iloc[::-1]))
    assert back == pytest.approx(ahead[::-1])


def test_the_network_learns_that_decided_cases_finish_sooner():
    pytest.importorskip("torch")
    from soudai import network

    rng = np.random.default_rng(1)
    made = []
    for number in range(400):
        if number % 2:  # decided within days of filing, legally final about a month later
            decided = int(rng.integers(5, 20))
            end = decided + int(rng.integers(25, 35))
            steps = [("ZAHAJ_RIZ", 0), ("VYD_ROZH", decided), ("ST_VEC_VYR", decided), ("ST_VEC_PUK", end)]
        else:  # a hearing about 10 months in
            heard = int(rng.integers(280, 320))
            steps = [("ZAHAJ_RIZ", 0), ("NAR_JED", heard), ("VYD_ROZH", heard), ("ST_VEC_PUK", heard + 30)]
        made.append(case(number, "OSVYCNA", steps))
    built = made_up_examples(made)
    model, history = network.fit(built, log=lambda _: None)
    assert history[-1] < history[0]
    at = built.cuts[built.cuts["day"] == built.steps["day"].to_numpy()[built.cuts["step"]]]
    at = at[at["step"].map(built.steps["code"]).isin(["ST_VEC_VYR", "ZAHAJ_RIZ"])]
    still = network.still_open(model, network.Data(built, at))
    decided = at["step"].map(built.steps["code"]).eq("ST_VEC_VYR").to_numpy()
    assert still[decided, 1].mean() < 0.3  # decided cases: mostly final within 2 months
    assert still[~decided & (at["day"] == 0).to_numpy(), 1].mean() > 0.4  # at filing, it's a mix


if __name__ == "__main__":
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(make_fixture(), indent=1)
    FIXTURE.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {FIXTURE}")
