"""The network's forward pass in plain numpy (milestone 7), for one case at a time. It's the reference for
the demo's JavaScript, which runs the network on made-up cases, and it needs no PyTorch: it reads the
weights that `network.weights` writes.

The GRU's update, as PyTorch computes it, for an event x and the hidden state h before it:

    r = σ(W_ir x + b_ir + W_hr h + b_hr)
    z = σ(W_iz x + b_iz + W_hz h + b_hz)
    n = tanh(W_in x + b_in + r ⊙ (W_hn h + b_hn))
    h' = (1 − z) ⊙ n + z ⊙ h

where W_i is `gru.weight_ih_l0` with its rows in the order r, z, n, and likewise W_h, b_i and b_h.
"""

import numpy as np


def _sigmoid(x):
    return 1 / (1 + np.exp(-x))


def still_open(weights, court, events, day):
    """The chance a case is still open 1, 2, ... months after day `day`, given its court (a code) and its
    events so far, as (code, days after filing) in order, from its filing on day 0. `day` counts from
    filing too, and is on or after the last event's."""
    state = {name: np.asarray(value, dtype=float) for name, value in weights["state"].items()}
    codes = {code: i for i, code in enumerate(weights["codes"])}
    courts = {code: i for i, code in enumerate(weights["courts"])}
    w_i, w_h = state["gru.weight_ih_l0"], state["gru.weight_hh_l0"]
    b_i, b_h = state["gru.bias_ih_l0"], state["gru.bias_hh_l0"]
    size = w_h.shape[1]
    h, previous = np.zeros(size), 0
    for code, when in events:
        x = np.concatenate([state["code.weight"][codes[code]], np.log1p([when - previous, when])])
        gi, gh = w_i @ x + b_i, w_h @ h + b_h
        r = _sigmoid(gi[:size] + gh[:size])
        z = _sigmoid(gi[size : 2 * size] + gh[size : 2 * size])
        n = np.tanh(gi[2 * size :] + r * gh[2 * size :])
        h, previous = (1 - z) * n + z * h, when
    x = np.concatenate([h, state["court.weight"][courts[court]], np.log1p([day - previous, day])])
    layer = np.maximum(state["layer.weight"] @ x + state["layer.bias"], 0)
    finishing = _sigmoid(state["out.weight"] @ layer + state["out.bias"])
    return np.cumprod(1 - finishing)
