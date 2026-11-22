"""The German tank estimate and its bounds: hand-worked values, the exact maths and brute-force simulation."""

import math

import numpy as np
import pytest

from soudai import tank


def sample_maxima(rng, n, k, repetitions):
    """The highest of k distinct numbers drawn at random from 1..n, `repetitions` times. The k numbers are
    the ones given the k smallest of n random keys."""
    keys = rng.random((repetitions, n))
    return (np.argpartition(keys, k - 1, axis=1)[:, :k] + 1).max(axis=1)


def chance_of_max(m, k, n):
    """P(the highest of k distinct numbers from 1..n is m), exactly, as a float."""
    return math.comb(m - 1, k - 1) / math.comb(n, k)


def test_the_estimate_on_hand_worked_values():
    assert tank.estimate(60, 4) == 74  # 60 × 5/4 − 1
    assert tank.estimate(1, 1) == 1
    assert tank.estimate(100, 3) == pytest.approx(100 * 4 / 3 - 1)
    assert tank.estimate(10, 10) == 10  # every number from 1 to 10 published: exactly 10
    assert tank.estimate(0, 0) is None


@pytest.mark.parametrize("m, k", [(3, 4), (0, 1), (5, -1), (-1, 0)])
def test_impossible_samples_are_refused(m, k):
    with pytest.raises(ValueError):
        tank.estimate(m, k)
    with pytest.raises(ValueError):
        tank.upper_bound(m, k)


def test_bad_arguments_are_refused():
    with pytest.raises(TypeError):
        tank.estimate(10.5, 2)
    for confidence in (0, 1, 1.5):
        with pytest.raises(ValueError):
            tank.upper_bound(10, 2, confidence)


@pytest.mark.parametrize("n, k", [(1, 1), (50, 1), (50, 7), (400, 100), (30, 30)])
def test_the_estimate_is_unbiased_exactly(n, k):
    mean = sum(chance_of_max(m, k, n) * tank.estimate(m, k) for m in range(k, n + 1))
    assert mean == pytest.approx(n, rel=1e-12)


@pytest.mark.parametrize("n, k", [(50, 1), (400, 3), (400, 40)])
def test_the_estimate_is_unbiased_in_simulation(n, k):
    rng = np.random.default_rng(1)
    estimates = np.array([tank.estimate(m, k) for m in sample_maxima(rng, n, k, 10_000)])
    error = estimates.std() / math.sqrt(len(estimates))
    assert abs(estimates.mean() - n) < 4 * error


def test_the_upper_bound_on_hand_worked_values():
    # k = 1: P(N) = m/N, so the bound is 20m, where P is exactly 1/20.
    assert tank.upper_bound(1, 1) == 20
    assert tank.upper_bound(7, 1) == 140
    assert tank.upper_bound(1, 1, 0.9) == 10
    assert tank.upper_bound(5, 5) == 6  # 1/C(6, 5) = 1/6 ≥ 1/20 > 1/C(7, 5) = 1/21
    assert tank.upper_bound(60, 60) == 60  # 1/C(61, 60) = 1/61 is already below 1/20
    assert tank.upper_bound(0, 0) is None


LARGE = [(20_000, 500), (30_000, 1), (30_000, 3000)]


@pytest.mark.parametrize("m, k", [(1, 1), (7, 1), (3, 2), (60, 4), (5, 5), (60, 60), (400, 100), *LARGE])
@pytest.mark.parametrize("confidence, one_in", [(0.95, 20), (0.9, 10), (0.99, 100)])
def test_the_upper_bound_is_exact_at_the_boundary(m, k, confidence, one_in):
    """P(U) = C(m, k)/C(U, k) ≥ 1/one_in, and P(U + 1) < 1/one_in, in whole numbers."""
    bound = tank.upper_bound(m, k, confidence)
    assert bound >= m
    assert math.comb(bound, k) <= one_in * math.comb(m, k) < math.comb(bound + 1, k)


@pytest.mark.parametrize("k", [1, 3, 20, 100])
def test_the_upper_bound_covers_n_95_percent_of_the_time(k):
    """At least 95%, and only by as much as the discreteness of the highest number forces."""
    n, repetitions = 400, 10_000
    bounds = {m: tank.upper_bound(m, k) for m in range(k, n + 1)}
    exact = sum(chance_of_max(m, k, n) for m, bound in bounds.items() if bound >= n)
    assert 0.95 <= exact < 0.965
    maxima = sample_maxima(np.random.default_rng(2), n, k, repetitions)
    simulated = np.mean([bounds[m] >= n for m in maxima])
    assert abs(simulated - exact) < 4 * math.sqrt(exact * (1 - exact) / repetitions)


def test_a_senate_counts_each_case_once():
    assert tank.senate([3, 7, 7, 1, 3, 7]) == tank.senate([1, 3, 7])
    assert tank.senate([1, 3, 7]) == (7, 3, tank.estimate(7, 3), tank.upper_bound(7, 3))
    assert tank.senate([]) == (0, 0, None, None)
    with pytest.raises(ValueError):
        tank.senate([0, 4])


def test_a_courts_estimate_and_lower_bound_are_sums():
    total = tank.court_total([(60, 4), (10, 10)])
    assert (total["estimate"], total["lower"]) == (84, 70)
    assert total == tank.court_total([(60, 4), (10, 10)])  # the same seed, the same bound
    assert tank.court_total([]) is None
    with pytest.raises(ValueError):
        tank.court_total([(60, 4), (0, 0)])


def test_a_court_with_every_number_published_is_counted_exactly():
    total = tank.court_total([(200, 200), (300, 300), (250, 250)])
    assert total == {"estimate": 750, "lower": 750, "upper": 750}


@pytest.mark.parametrize("m, k", [(400, 100), (380, 50), (2000, 400), (60, 60)])
def test_one_senates_simulated_bound_is_its_upper_bound(m, k):
    """For a narrow confidence distribution, to within 1."""
    assert abs(tank.court_total([(m, k)])["upper"] - tank.upper_bound(m, k)) <= 1


@pytest.mark.parametrize("m, k", [(100, 1), (100, 3), (1000, 2)])
def test_one_senates_simulated_bound_is_at_the_right_percentile(m, k):
    """For a wide one, the simulation's noise is many numbers wide, so compare the chances instead: P at the
    simulated bound is 1/20, to within the noise of a percentile of 20,000 draws."""
    bound = tank.court_total([(m, k)])["upper"]
    chance = math.comb(m, k) / math.comb(bound, k)
    assert abs(chance - 0.05) < 4 * math.sqrt(0.05 * 0.95 / tank.DRAWS)


@pytest.mark.parametrize(
    "ks",
    [
        [100, 200, 150, 300, 200],  # narrow senates, where the bound is tightest
        [2, 40, 1, 100, 10],  # senates with few numbers make it more conservative
    ],
)
def test_a_courts_upper_bound_covers_its_total(ks):
    sizes, repetitions = [400, 800, 300, 1200, 600], 1000
    rng = np.random.default_rng(3)
    maxima = np.array([sample_maxima(rng, n, k, repetitions) for n, k in zip(sizes, ks, strict=True)]).T
    covered = [
        tank.court_total(list(zip(row, ks, strict=True)), draws=2000, seed=i)["upper"] >= sum(sizes)
        for i, row in enumerate(maxima)
    ]
    assert np.mean(covered) >= 0.95 - 3 * math.sqrt(0.05 * 0.95 / repetitions)
