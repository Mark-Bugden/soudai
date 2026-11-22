"""The German tank estimate: how many cases a senate filed in a year, from its published decisions alone.

A senate numbers its civil cases 1..N each year. If the published decisions show k distinct case numbers,
the highest m, and those are a uniform random sample of 1..N:

- **Estimate.** N̂ = m(1 + 1/k) − 1, the unbiased estimate with the least variance.
- **Upper bound.** Out of 1..N, the highest of k numbers is at most m with probability
  P(N) = C(m, k) / C(N, k). The 95% upper bound is the largest N with P(N) ≥ 5%: any larger N would make a
  highest number as low as m too unlikely. The lower bound is m itself.
- **Court totals.** The estimate is the sum of the senates' estimates, and the lower bound the sum of their
  m. The upper bound comes from simulation: draw each senate's N from its confidence distribution, add them
  up, and take the 95th percentile. A senate's confidence distribution is the one whose percentiles are its
  upper bounds (P(draw ≥ n) = P(n)), so for one senate the simulation gives back `upper_bound`, give or
  take its noise. In simulation, the court's bound covers the true total about 95% of the time when every
  senate has many numbers, and more often when some have only a few, whose distributions have long tails.

The published numbers aren't a uniform sample (only decided cases are published, so recent high numbers
are missing), and the estimate runs low. How far it runs low, against the exact counts, is the finding: see
"The German tank estimate" in docs/plan.md.
"""

import math
import operator
from fractions import Fraction

import numpy as np
from scipy.special import gammaln

CONFIDENCE = 0.95
DRAWS = 20_000  # simulated totals per court
SEED = 0  # so a court's bound is the same on every run


def estimate(m, k):
    """The estimate of N, m(1 + 1/k) − 1, from k distinct numbers with highest m. None if k = 0."""
    m, k = _check(m, k)
    if k == 0:
        return None
    return m + m / k - 1


def upper_bound(m, k, confidence=CONFIDENCE):
    """The one-sided upper confidence bound for N: the largest N with C(m, k) / C(N, k) ≥ 1 − confidence.
    None if k = 0."""
    m, k = _check(m, k)
    if k == 0:
        return None
    alpha = _alpha(confidence)
    # Found in floating point, then settled exactly: C(m, k) / C(n, k) ≥ alpha, in whole numbers.
    top = math.comb(m, k) * alpha.denominator
    n = int(_largest(m, k, float(alpha)))
    while math.comb(n, k) * alpha.numerator > top:
        n -= 1
    while math.comb(n + 1, k) * alpha.numerator <= top:
        n += 1
    return n


def senate(numbers, confidence=CONFIDENCE):
    """(m, k, estimate, upper bound) from a senate-year's published case numbers. A case can have several
    published decisions, so each number counts once."""
    distinct = set(numbers)
    if distinct and min(distinct) < 1:
        raise ValueError(f"case numbers start at 1, not {min(distinct)}")
    m, k = max(distinct, default=0), len(distinct)
    return m, k, estimate(m, k), upper_bound(m, k, confidence)


def court_total(senates, confidence=CONFIDENCE, draws=DRAWS, seed=SEED):
    """A court's total from its senates' (m, k): {"estimate", "lower", "upper"}, or None if there are none.

    The estimate is the sum of the senates' estimates, the lower bound the sum of their m, and the upper
    bound the `confidence` quantile of `draws` simulated totals. Senates with no published numbers (k = 0)
    can't be estimated and aren't counted: leave them out, and report them as missed.
    """
    if not senates:
        return None
    pairs = [_check(*pair) for pair in senates]
    if any(k == 0 for _, k in pairs):
        raise ValueError("a senate with no published numbers (k = 0) can't be estimated: leave it out")
    m, k = np.array(pairs, dtype=float).T
    rng = np.random.default_rng(seed)
    # Each senate's N, drawn from its confidence distribution: the largest n with P(n) ≥ v, for v uniform
    # on (0, 1], so that P(draw ≥ n) = P(n). A row per senate, a column per draw.
    v = 1 - rng.random((len(pairs), draws))
    totals = _largest(m[:, None], k[:, None], v).sum(axis=0)
    return {
        "estimate": sum(estimate(*pair) for pair in pairs),
        "lower": sum(pair[0] for pair in pairs),
        "upper": int(np.quantile(totals, float(confidence), method="inverted_cdf")),
    }


def _check(m, k):
    """m and k as whole numbers, if k distinct numbers can have highest m."""
    m, k = operator.index(m), operator.index(k)
    if k < 0 or m < k:
        raise ValueError(f"{k} distinct numbers from 1 up can't have highest number {m}")
    return m, k


def _alpha(confidence):
    """1 − confidence as an exact fraction, reading confidence as the decimal it's written as: 0.95 gives
    exactly 1/20, so a tie at the boundary (k = 1, N = 20m) counts as inside."""
    alpha = 1 - Fraction(str(confidence))
    if not 0 < alpha < 1:
        raise ValueError(f"confidence must be between 0 and 1, not {confidence}")
    return alpha


def _largest(m, k, v):
    """The largest n ≥ m with C(m, k) / C(n, k) ≥ v, for k ≥ 1 and v in (0, 1], in floating point. m, k and
    v can be arrays that broadcast together.

    For n ≥ m and i < k, (m − i) / (n − i) lies between (m − k + 1) / (n − k + 1) and m / n, so the ratio,
    their product over i, lies between ((m − k + 1) / (n − k + 1))^k and (m / n)^k. Those bracket the answer
    to within about (k − 1)(v^(−1/k) − 1) (exactly when k = 1, and to a few numbers when k is large), and a
    bisection finishes it.
    """
    log_v = np.log(v)
    grow = np.exp(-log_v / k)  # v^(−1/k)
    lo = np.maximum(m, np.floor(k - 1 + (m - k + 1) * grow) - 1)  # inside: the ratio there is ≥ v
    hi = np.ceil(m * grow) + 1  # outside: the ratio there is < v
    log_top = _log_falling(m, k)
    while (open_ := hi - lo > 1).any():
        mid = np.floor((lo + hi) / 2)
        inside = log_top - _log_falling(mid, k) >= log_v
        lo = np.where(open_ & inside, mid, lo)
        hi = np.where(open_ & ~inside, mid, hi)
    return lo


def _log_falling(n, k):
    """log(n (n − 1) ... (n − k + 1)). C(m, k) / C(n, k) is the ratio of two of these."""
    return gammaln(n + 1) - gammaln(n - k + 1)
