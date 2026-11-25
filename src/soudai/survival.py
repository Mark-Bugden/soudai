"""Weighted survival estimates: how long until something happens, when some cases haven't got there yet.

A case that hasn't reached the event by the day its record runs to is censored: it took at least that
long, but how much longer isn't known. The Kaplan–Meier estimate counts such a case for as long as it's
known to be waiting, rather than dropping it, which would make waits look shorter. Where a case can leave
in more than one way (from a filing to a hearing, or straight to a decision, say), the Aalen–Johansen
estimate shares the Kaplan–Meier curve out between the ways: its cumulative incidence of a way is the
share of cases that have left that way by each time.

Every sampled case stands for `weight` real cases, so a count of cases is a sum of weights. On a day when
some cases leave and others are censored, the censored ones still count as waiting, as usual.
"""

import numpy as np


def table(durations, causes, weights=None):
    """The life table: the times at which cases leave, the weight still waiting just before each, and the
    weight leaving at each, by way out. `causes` is 0 for a censored case, or k ≥ 1 for one that left by
    way k. Returns (times, waiting, leaving), with `leaving` of shape (len(times), ways)."""
    durations = np.asarray(durations, dtype=float)
    causes = np.asarray(causes, dtype=int)
    weights = np.ones(len(durations)) if weights is None else np.asarray(weights, dtype=float)
    order = np.argsort(durations, kind="stable")
    durations, causes, weights = durations[order], causes[order], weights[order]
    times, first = np.unique(durations, return_index=True)
    waiting = weights.sum() - np.concatenate([[0.0], np.cumsum(weights)])[first]
    leaving = np.zeros((len(times), causes.max(initial=0)))
    at = np.searchsorted(times, durations)
    for way in range(1, leaving.shape[1] + 1):
        np.add.at(leaving[:, way - 1], at[causes == way], weights[causes == way])
    keep = leaving.sum(axis=1) > 0
    return times[keep], waiting[keep], leaving[keep]


def kaplan_meier(durations, ended, weights=None):
    """The share still waiting just after each time a case leaves: (times, share)."""
    times, waiting, leaving = table(durations, np.asarray(ended, dtype=int), weights)
    return times, np.cumprod(1 - leaving.sum(axis=1) / waiting)


def cumulative_incidence(durations, causes, weights=None):
    """The Aalen–Johansen estimate: (times, incidence), where incidence[:, k - 1] is the share of cases
    that have left by way k by each time. The ways' shares and the share still waiting add up to 1."""
    times, waiting, leaving = table(durations, causes, weights)
    still = np.cumprod(1 - leaving.sum(axis=1) / waiting)
    before = np.concatenate([[1.0], still[:-1]])
    return times, np.cumsum(before[:, None] * leaving / waiting[:, None], axis=0)


def quantile(times, reached, q):
    """The first time by which `reached`, a share rising from 0, is at least q. None if it never is."""
    i = np.searchsorted(reached, q - 1e-9)
    return times[i] if i < len(times) else None


def at(times, values, grid, before):
    """A step function's values at the times in `grid`: `values[i]` from `times[i]` on, and `before`
    until the first."""
    i = np.searchsorted(times, grid, side="right") - 1
    return np.where(i >= 0, values[np.maximum(i, 0)] if len(values) else before, before)
