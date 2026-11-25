"""The scores: concordance against lifelines and by hand, and the Brier score and calibration by hand."""

import numpy as np
import pandas as pd
import pytest
from lifelines.utils import concordance_index

from soudai import scoring
from soudai.examples import HORIZON, MONTH


def random_outcomes(seed, n=300):
    rng = np.random.default_rng(seed)
    left = rng.integers(1, 60, n)  # few distinct days, so plenty of ties
    ended = rng.random(n) < 0.7
    score = np.round(left + rng.normal(0, 15, n))  # tied scores too
    return score, left, ended, rng.integers(1, 4, n).astype(float)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_concordance_matches_lifelines_unweighted(seed):
    score, left, ended, _ = random_outcomes(seed)
    expected = concordance_index(left, score, ended)
    assert scoring.concordance(score, left, ended, np.ones(len(left))) == pytest.approx(expected)


@pytest.mark.parametrize("seed", [4, 5])
def test_a_weight_counts_as_that_many_copies(seed):
    score, left, ended, weights = random_outcomes(seed)
    copies = weights.astype(int)
    repeated = [np.repeat(a, copies) for a in (score, left, ended)]
    expected = scoring.concordance(*repeated, np.ones(copies.sum()))
    assert scoring.concordance(score, left, ended, weights) == pytest.approx(expected)


def test_concordance_by_hand():
    # A ends on day 10, B on day 20, C censored on day 15, D censored on day 10. The pairs: A before B, C
    # and D (D censored the day A ended counts as still open), and C before nothing, since it's censored.
    left, ended = [10, 20, 15, 10], [True, True, False, False]
    weights = [1, 2, 3, 4]
    score = [1, 3, 2, 1]  # A is right against B and C, and ties with D
    pairs = 1 * (2 + 3 + 4)
    assert scoring.concordance(score, left, ended, weights) == pytest.approx((2 + 3 + 4 / 2) / pairs)


def flat(chances):
    """Forecasts with the given chance of still being open at every month."""
    return np.repeat(np.asarray(chances, dtype=float)[:, None], HORIZON, axis=1)


def test_expected_months_is_the_area_under_the_curve():
    assert scoring.expected_months(flat([1.0, 0.0])).tolist() == [HORIZON, 1]


def test_brier_without_censoring_is_the_weighted_squared_error():
    still = flat([0.2, 0.5, 0.9])
    left = np.array([10, 100, 400])
    ended = np.array([True, True, True])
    weights = np.array([1.0, 2.0, 3.0])
    # at 3 months (91.3 days) the first finished, and the others hadn't
    expected = (1 * (1 - 0.8) ** 2 + 2 * (0 - 0.5) ** 2 + 3 * (0 - 0.1) ** 2) / 6
    assert scoring.brier(still, left, ended, weights, 3) == pytest.approx(expected)


def test_brier_with_censoring_by_hand():
    # Four cases of weight 1. A finished on day 10; B was censored on day 20; C finished on day 40; D was
    # still open past 2 months. The censoring curve G is 1 until day 20, then 2/3 (B of the 3 still open).
    still = flat([0.5, 0.5, 0.5, 0.5])
    left = np.array([10, 20, 40, 100])
    ended = np.array([True, False, True, False])
    weights = np.ones(4)
    ipcw = scoring.censoring_weights(left, ended, weights, 2)
    assert ipcw == pytest.approx([1, 0, 3 / 2, 3 / 2])
    expected = (1 * 0.25 + 0 + 1.5 * 0.25 + 1.5 * 0.25) / 4
    assert scoring.brier(still, left, ended, weights, 2) == pytest.approx(expected)


def test_calibration_by_hand():
    still = flat([0.95, 0.95, 0.35, 0.35, 0.35, 0.35])  # forecasts of 5% and 65% within a month
    left = np.array([10, 300, 10, 10, 300, 300])
    ended = np.ones(6, dtype=bool)
    weights = np.array([1.0, 1.0, 1.0, 2.0, 1.0, 1.0])
    table = scoring.calibration(still, left, ended, weights, 1).set_index("bin")
    assert table.index.tolist() == [0, 6]
    columns = ["weight", "sampled", "forecast", "observed"]
    assert table.loc[0, columns].tolist() == pytest.approx([2, 2, 0.05, 0.5])
    assert table.loc[6, ["weight", "observed"]].tolist() == pytest.approx([5, 3 / 5])
    assert scoring.calibration_error(table) == pytest.approx((2 * 0.45 + 5 * 0.05) / 7)


def test_score_pools_concordance_over_landmarks_only():
    # Two landmarks whose cases would be ranked wrongly against each other, but rightly within each
    cuts = pd.DataFrame(
        {
            "landmark": [0, 0, 6, 6],
            "left": [10, 20, 30, 40],
            "ended": [True] * 4,
            "weight": [1.0] * 4,
        }
    )
    still = flat([0.8, 0.9, 0.1, 0.2])
    out = scoring.score(still, cuts)
    assert out["concordance"] == 1.0
    assert out["cuts"] == 4 and out["weight"] == 4
    # within a month (30.4 days), the first three finished, with forecasts of 20%, 10% and 90%, and the
    # last didn't, with 80%
    assert 30 < MONTH < 40
    assert out["brier_1"] == pytest.approx(np.mean([0.8**2, 0.9**2, 0.1**2, 0.8**2]))
