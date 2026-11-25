"""The weighted Kaplan–Meier and Aalen–Johansen estimates, by hand and against lifelines."""

import numpy as np
import pytest
from lifelines import AalenJohansenFitter, KaplanMeierFitter

from soudai import survival

# Five cases: one leaves by way 1 on day 1; on day 2 one leaves by way 2 and one weighing 2 is censored;
# one leaves by way 1 on day 3.
DURATIONS, CAUSES, WEIGHTS = [1, 2, 2, 3], [1, 2, 0, 1], [1, 1, 2, 1]


def test_the_life_table_by_hand():
    times, waiting, leaving = survival.table(DURATIONS, CAUSES, WEIGHTS)
    assert times.tolist() == [1, 2, 3]
    assert waiting.tolist() == [5, 4, 1]  # the case censored on day 2 still counts as waiting then
    assert leaving.tolist() == [[1, 0], [0, 1], [1, 0]]


def test_kaplan_meier_by_hand():
    times, still = survival.kaplan_meier(DURATIONS, np.array(CAUSES) > 0, WEIGHTS)
    assert times.tolist() == [1, 2, 3]
    assert still == pytest.approx([4 / 5, 4 / 5 * 3 / 4, 0])


def test_cumulative_incidence_by_hand():
    times, incidence = survival.cumulative_incidence(DURATIONS, CAUSES, WEIGHTS)
    assert incidence[:, 0] == pytest.approx([1 / 5, 1 / 5, 1 / 5 + 3 / 5])
    assert incidence[:, 1] == pytest.approx([0, 1 / 5, 1 / 5])
    _, still = survival.kaplan_meier(DURATIONS, np.array(CAUSES) > 0, WEIGHTS)
    assert incidence.sum(axis=1) + still == pytest.approx(1)


def random_cases(seed, n=400, ties=True):
    rng = np.random.default_rng(seed)
    durations = rng.exponential(100, n)
    durations = np.round(durations) if ties else durations
    causes = rng.choice([0, 1, 2, 3], n, p=[0.2, 0.5, 0.2, 0.1])
    return durations, causes, rng.integers(1, 30, n).astype(float)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_kaplan_meier_matches_lifelines_with_weights_and_ties(seed):
    durations, causes, weights = random_cases(seed)
    times, still = survival.kaplan_meier(durations, causes > 0, weights)
    fit = KaplanMeierFitter().fit(durations, causes > 0, weights=weights)
    assert still == pytest.approx(fit.survival_function_at_times(times).to_numpy())


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_cumulative_incidence_matches_lifelines_with_weights(seed):
    durations, causes, weights = random_cases(seed, ties=False)  # lifelines jitters ties at random
    times, incidence = survival.cumulative_incidence(durations, causes, weights)
    for way in (1, 2, 3):
        fit = AalenJohansenFitter(calculate_variance=False).fit(durations, causes, way, weights=weights)
        expected = fit.cumulative_density_.iloc[:, 0]
        assert incidence[:, way - 1] == pytest.approx(expected.reindex(times).to_numpy())


def test_one_way_out_is_one_minus_kaplan_meier():
    durations, causes, weights = random_cases(4)
    _, still = survival.kaplan_meier(durations, causes > 0, weights)
    _, incidence = survival.cumulative_incidence(durations, (causes > 0).astype(int), weights)
    assert incidence[:, 0] == pytest.approx(1 - still)


def test_quantiles_and_values_at_given_times():
    times, still = survival.kaplan_meier([1, 2, 3, 4], [1, 1, 1, 1])
    assert survival.quantile(times, 1 - still, 0.5) == 2
    assert survival.quantile(times, 1 - still, 0.75) == 3
    assert survival.quantile(times[:2], 1 - np.array([1.0, 0.9]), 0.5) is None  # never half
    assert survival.at(times, still, [0, 1, 1.5, 4, 9], before=1.0).tolist() == [1, 0.75, 0.75, 0, 0]


def test_nobody_leaving_gives_empty_curves():
    times, still = survival.kaplan_meier([5, 6], [0, 0])
    assert len(times) == 0 and len(still) == 0
    assert survival.at(times, still, [0, 10], before=1.0).tolist() == [1, 1]
