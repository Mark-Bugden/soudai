"""The court average and the process map, on made-up training examples worked by hand."""

import numpy as np
import pandas as pd
import pytest

from soudai import baselines
from soudai.examples import HORIZON, MONTH, Examples


def training(histories=None, cuts=None):
    return Examples(pd.DataFrame(histories or []), pd.DataFrame(), pd.DataFrame(cuts or []))


def test_the_court_average_reads_the_courts_curve_from_the_cuts_day(monkeypatch):
    monkeypatch.setattr(baselines, "MIN_AT_RISK", 1)
    # Court A: cases finishing on days 20, 50 and 100, weighing 1, 1 and 2, and one censored on day 70.
    # Court B: one case finishing on day 400.
    histories = [
        {"court": "A", "span": 20, "ended": True, "weight": 1.0},
        {"court": "A", "span": 50, "ended": True, "weight": 1.0},
        {"court": "A", "span": 70, "ended": False, "weight": 1.0},
        {"court": "A", "span": 100, "ended": True, "weight": 2.0},
        {"court": "B", "span": 400, "ended": True, "weight": 1.0},
    ]
    cuts = pd.DataFrame({"court": ["A", "A", "B"], "day": [0, 40, 0]})
    still = baselines.court_average(training(histories), cuts)
    assert still.shape == (3, HORIZON)
    # From filing: S(20) = 4/5, S(50) = 4/5 * 3/4 = 3/5, then S(100) = 0. A month is 30.4 days.
    assert still[0, :4].tolist() == pytest.approx([4 / 5, 3 / 5, 3 / 5, 0])
    # From day 40, when S = 4/5: day 70.4 gives 3/5 / (4/5), and day 100.9 gives 0
    assert still[1, :3].tolist() == pytest.approx([3 / 4, 0, 0])
    assert still[2, 12] == 1 and still[2, 13] == 0  # 13 months is 395.7 days, 14 is 426.1


def test_the_court_average_stops_reading_where_few_cases_are_left(monkeypatch):
    monkeypatch.setattr(baselines, "MIN_AT_RISK", 2)
    histories = [{"court": "A", "span": span, "ended": True, "weight": 1.0} for span in (10, 40, 300)]
    cuts = pd.DataFrame({"court": ["A", "A"], "day": [39, 200]})
    still = baselines.court_average(training(histories), cuts)
    # Only one case is open after day 39, so a cut on day 200 is read as if on day 39
    assert still[1] == pytest.approx(still[0])
    assert still[0, :2].tolist() == pytest.approx([1 / 2, 1 / 2])


def test_the_process_map_uses_the_court_stage_and_days_in_stage(monkeypatch):
    monkeypatch.setattr(baselines, "MIN_CUTS", 2)
    rows = []
    # Court A, "decided" on its first day: two cuts, with 10 and 40 days left
    rows += [{"court": "A", "stage": "decided", "in_stage": 0, "left": d, "ended": True} for d in (10, 40)]
    # Court A, "decided" 31-91 days in: only one cut, so all courts' cuts are used, with court B's
    rows += [{"court": "A", "stage": "decided", "in_stage": 50, "left": 100, "ended": True}]
    rows += [{"court": "B", "stage": "decided", "in_stage": 60, "left": 200, "ended": True}]
    # "filed" 1-30 days in has one cut, so all of "filed" is used
    rows += [{"court": "A", "stage": "filed", "in_stage": 0, "left": d, "ended": True} for d in (5, 300)]
    rows += [{"court": "A", "stage": "filed", "in_stage": 10, "left": 70, "ended": True}]
    train = training(cuts=[row | {"weight": 1.0} for row in rows])
    cuts = pd.DataFrame(
        {"court": ["A", "A", "A"], "stage": ["decided", "decided", "filed"], "in_stage": [0, 80, 20]}
    )
    still = baselines.process_map(train, cuts)
    assert still[0, :3].tolist() == pytest.approx([1 / 2, 0, 0])
    # 100 and 200 days left: month 3 ends on day 91.3, month 4 on day 121.8 and month 7 on day 213.1
    assert still[1, :8].tolist() == pytest.approx([1, 1, 1, 1 / 2, 1 / 2, 1 / 2, 0, 0])
    assert still[2, :3].tolist() == pytest.approx([2 / 3, 2 / 3, 1 / 3])  # 5, 70 and 300 days left
    assert np.diff(still, axis=1).max() <= 0
    assert 300 / MONTH < 10
