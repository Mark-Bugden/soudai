"""The remaining-time network (milestone 7), in PyTorch, which is in the optional `model` dependency group.

A GRU (a recurrent network) reads a case's events in order, updating a hidden state of HIDDEN numbers after
each. At a cut, the output layers read the hidden state after the last event so far, the court and the
time since that event and since filing, and give the chance the case finishes in each of the next HORIZON
months, given that it's still open at the start of that month (a discrete-time hazard, or "logistic
hazard"). The chance it's still open after k months is the product of 1 − those chances up to month k.

- **An event** is its type, as CODE learned numbers, then log(1 + days since the previous event) and
  log(1 + days since filing).
- **The output layers** take the hidden state, the court as COURT learned numbers, log(1 + days since the
  last event) and log(1 + days since filing), through a layer of LAYER with ReLU, then one of HORIZON.
- **The loss** for a cut that finished in month k is −[log(1 − p₁) + … + log(1 − p_{k−1}) + log p_k], and
  for one known to be open after n months, −[log(1 − p₁) + … + log(1 − p_n)]. Each cut counts with its
  case's weight, and the loss is per month a case is known to be open at the start of, as the trees'.
- **Training** reads all of a case's cuts in one pass. Adam, batches of BATCH cases, stopping when the loss
  on the held-out cases hasn't improved for PATIENCE passes over the data.

`sequence=False` gives the same output layers fed the hand-made features (`baselines.features`) instead of
the hidden state: it separates "a neural network helps" from "reading the sequence helps".

`weights` writes the network as plain numbers, for `forward`, which runs it without PyTorch, as the demo
does.
"""

import copy
import time

import numpy as np
import torch
from torch import nn

from . import baselines, examples, reference
from .examples import HORIZON, MONTH

CODES = sorted(row["code"] for row in reference.events() if row["kind"] == "event")
COURTS = sorted(row["code"] for row in reference.courts())
CODE, HIDDEN, COURT, LAYER = 8, 32, 4, 32
BATCH, RATE, EPOCHS, PATIENCE = 256, 1e-3, 80, 5


class Network(nn.Module):
    def __init__(self, sequence=True):
        super().__init__()
        self.sequence = sequence
        if sequence:
            self.code = nn.Embedding(len(CODES), CODE)
            self.gru = nn.GRU(CODE + 2, HIDDEN, batch_first=True)
        self.court = nn.Embedding(len(COURTS), COURT)
        state = HIDDEN if sequence else len(baselines.FEATURES)
        self.layer = nn.Linear(state + COURT + 2, LAYER)
        self.out = nn.Linear(LAYER, HORIZON)

    def forward(self, batch):
        """The logits of each month's chance of finishing, for each cut in the batch."""
        if self.sequence:
            steps = torch.cat([self.code(batch["codes"]), batch["numbers"]], dim=2)
            hidden, _ = self.gru(steps)
            state = hidden[batch["row"], batch["position"]]
        else:
            state = batch["features"]
        x = torch.cat([state, self.court(batch["court"]), batch["at_cut"]], dim=1)
        return self.out(torch.relu(self.layer(x)))


class Data:
    """A set of cuts and their cases' events, as arrays the network reads. The cuts are kept sorted by
    case; `order` puts them back in the order given."""

    def __init__(self, ex, cuts):
        self.order = np.argsort(cuts["id"].to_numpy(), kind="stable")
        cuts = cuts.iloc[self.order]
        steps = ex.steps
        code = {c: i for i, c in enumerate(CODES)}
        self.codes = steps["code"].map(code).to_numpy(np.int64)
        self.numbers = np.log1p(steps[["gap", "day"]].to_numpy(np.float32))
        case_ids = steps["id"].to_numpy()
        self.ids = np.unique(cuts["id"].to_numpy())
        self.start = np.searchsorted(case_ids, self.ids)
        self.length = np.searchsorted(case_ids, self.ids, side="right") - self.start
        cut_ids = cuts["id"].to_numpy()
        self.cut_start = np.searchsorted(cut_ids, self.ids)
        self.cut_count = np.searchsorted(cut_ids, self.ids, side="right") - self.cut_start
        self.position = cuts["step"].to_numpy() - self.start[np.searchsorted(self.ids, cut_ids)]
        self.at_cut = np.log1p(cuts[["since_last", "day"]].to_numpy(np.float32))
        court = {c: i for i, c in enumerate(COURTS)}
        self.court = cuts["court"].map(court).to_numpy(np.int64)
        self.features = baselines.features(cuts).to_numpy(np.float32)
        left, ended = cuts["left"].to_numpy(), cuts["ended"].to_numpy()
        finished = np.ceil(left / MONTH).astype(int)
        self.finished = np.where(ended & (finished <= HORIZON), finished, 0)  # 0: not within the horizon
        open_for = np.minimum(np.floor(left / MONTH).astype(int), HORIZON)
        self.known = np.where(self.finished > 0, self.finished - 1, open_for)
        self.weight = cuts["weight"].to_numpy(np.float32)

    def batches(self, rng=None, size=BATCH):
        """Lists of case rows, of similar lengths, shuffled if given a random generator."""
        cases = np.arange(len(self.ids)) if rng is None else rng.permutation(len(self.ids))
        chunks = [cases[i : i + size * 50] for i in range(0, len(cases), size * 50)]
        out = []
        for chunk in chunks:
            chunk = chunk[np.argsort(self.length[chunk], kind="stable")]
            out += [chunk[i : i + size] for i in range(0, len(chunk), size)]
        return out if rng is None else [out[i] for i in rng.permutation(len(out))]

    def batch(self, cases):
        """The tensors for some cases (rows of `ids`) and all their cuts, and the cuts' rows."""
        length = self.length[cases]
        width = max(int(length.max()), 1)
        row = np.repeat(np.arange(len(cases)), length)
        col = np.arange(len(row)) - np.repeat(np.cumsum(length) - length, length)
        steps = np.repeat(self.start[cases], length) + col
        codes = np.zeros((len(cases), width), dtype=np.int64)
        numbers = np.zeros((len(cases), width, 2), dtype=np.float32)
        codes[row, col], numbers[row, col] = self.codes[steps], self.numbers[steps]
        count = self.cut_count[cases]
        cuts = np.repeat(self.cut_start[cases], count) + (
            np.arange(count.sum()) - np.repeat(np.cumsum(count) - count, count)
        )
        out = {
            "codes": torch.from_numpy(codes),
            "numbers": torch.from_numpy(numbers),
            "row": torch.from_numpy(np.repeat(np.arange(len(cases)), count)),
            "position": torch.from_numpy(self.position[cuts]),
            "court": torch.from_numpy(self.court[cuts]),
            "at_cut": torch.from_numpy(self.at_cut[cuts]),
            "features": torch.from_numpy(self.features[cuts]),
            "finished": torch.from_numpy(self.finished[cuts]),
            "known": torch.from_numpy(self.known[cuts]),
            "weight": torch.from_numpy(self.weight[cuts]),
        }
        return out, cuts


def loss_terms(logits, batch):
    """(the weighted loss summed over the cuts, the weighted number of months it's over)."""
    month = torch.arange(HORIZON)
    open_ = (month[None, :] < batch["known"][:, None]).float()
    finish = (month[None, :] == batch["finished"][:, None] - 1).float()
    log_open, log_finish = nn.functional.logsigmoid(-logits), nn.functional.logsigmoid(logits)
    per_cut = -(open_ * log_open + finish * log_finish).sum(dim=1)
    rows = open_.sum(dim=1) + finish.sum(dim=1)
    return (batch["weight"] * per_cut).sum(), (batch["weight"] * rows).sum()


def evaluate(model, data):
    """The held-out loss, per month a case is known to be open at the start of."""
    model.eval()
    total = rows = 0.0
    with torch.no_grad():
        for cases in data.batches(size=1024):
            batch, _ = data.batch(cases)
            loss, n = loss_terms(model(batch), batch)
            total, rows = total + loss.item(), rows + n.item()
    return total / rows


def fit(train, sequence=True, log=print, seed=examples.SEED):
    """The network fitted on the training cases, stopped on the held-out ones. Returns (network, the
    held-out loss after each pass). It's trained on one thread: PyTorch's sums over several threads come
    out slightly different from run to run, and the network is too small to gain from them."""
    threads = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        return _fit(train, sequence, log, seed)
    finally:
        torch.set_num_threads(threads)


def _fit(train, sequence, log, seed):
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    held = examples.held_out(train.histories)[train.cuts["id"].to_numpy()]
    fitting, checking = Data(train, train.cuts[~held]), Data(train, train.cuts[held])
    model = Network(sequence)
    optimiser = torch.optim.Adam(model.parameters(), lr=RATE)
    best, best_state, history, waited = np.inf, None, [], 0
    for epoch in range(EPOCHS):
        start = time.time()
        model.train()
        for cases in fitting.batches(rng):
            batch, _ = fitting.batch(cases)
            loss, rows = loss_terms(model(batch), batch)
            optimiser.zero_grad()
            (loss / rows).backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimiser.step()
        history.append(evaluate(model, checking))
        log(f"  pass {epoch + 1}: held-out loss {history[-1]:.6f} ({time.time() - start:.0f} s)")
        if history[-1] < best - 1e-6:
            best, best_state, waited = history[-1], copy.deepcopy(model.state_dict()), 0
        else:
            waited += 1
            if waited >= PATIENCE:
                break
    model.load_state_dict(best_state)
    return model, history


def still_open(model, data):
    """The chance each cut's case is still open 1, 2, ... HORIZON months later, in the order given."""
    model.eval()
    out = np.empty((len(data.weight), HORIZON))
    with torch.no_grad():
        for cases in data.batches(size=1024):
            batch, cuts = data.batch(cases)
            out[cuts] = torch.cumprod(torch.sigmoid(-model(batch)), dim=1).numpy()
    back = np.empty_like(out)
    back[data.order] = out
    return back


def weights(model):
    """The network as plain lists of numbers, to 9 significant digits (all a 32-bit float has), with the
    event codes and courts its rows stand for."""
    state = {
        name: np.vectorize(lambda x: float(f"{x:.9g}"), otypes=[float])(value.numpy()).tolist()
        for name, value in model.state_dict().items()
    }
    return {"codes": CODES, "courts": COURTS, "horizon": HORIZON, "state": state}
