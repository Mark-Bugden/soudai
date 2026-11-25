// The network's forward pass, ported from src/soudai/forward.py: the chance a case is still open 1, 2,
// ... 36 months on, from its court and its events so far. The forecast is the mean of the ensemble's
// networks' forecasts. No DOM access.
//
// The GRU's update, as PyTorch computes it, for an event x and the hidden state h before it:
//
//   r = σ(W_ir x + b_ir + W_hr h + b_hr)
//   z = σ(W_iz x + b_iz + W_hz h + b_hz)
//   n = tanh(W_in x + b_in + r ⊙ (W_hn h + b_hn))
//   h' = (1 − z) ⊙ n + z ⊙ h
//
// where W_i is `gru.weight_ih_l0` with its rows in the order r, z, n, and likewise W_h, b_i and b_h.
// Each event x is its code's 8 learned numbers, then log(1 + days since the previous event) and
// log(1 + days since filing). The output layers read the last hidden state, the court's 4 learned
// numbers, log(1 + days since the last event) and log(1 + days since filing).

/** Days in a month, as the model counts them. */
export const MONTH = 365.25 / 12;

/** A matrix the export stored as 16-bit integers with one scale, as { shape, values: Float64Array }. */
export function decode({ shape, scale, values }) {
  const bytes = Uint8Array.from(atob(values), (c) => c.charCodeAt(0));
  const view = new DataView(bytes.buffer);
  const out = new Float64Array(bytes.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = view.getInt16(2 * i, true) * scale;
  return { shape, values: out };
}

/** A matrix given as nested lists (network.json, the Python fixture), as { shape, values: Float64Array }. */
export function fromLists(lists) {
  const shape = Array.isArray(lists[0]) ? [lists.length, lists[0].length] : [lists.length];
  return { shape, values: Float64Array.from(lists.flat()) };
}

/** The exported network (soudai.json's `network`), ready for `stillOpen`. */
export const network = (exported) => ({
  horizon: exported.horizon,
  members: exported.members.map((member) => mapValues(member, decode)),
});

/** A network as `network.weights` writes it, with every weight in full: for the tests. */
export const fullNetwork = (weights) => ({
  horizon: weights.horizon,
  members: weights.members.map((member) => mapValues(member, fromLists)),
});

const mapValues = (object, fn) => Object.fromEntries(Object.entries(object).map(([key, value]) => [key, fn(value)]));

/**
 * The chance a case is still open 1, 2, ... `horizon` months after day `day`, as a Float64Array, given
 * its court (its row in the network) and its events so far, as [code (its row), days after filing], in
 * order, from its filing on day 0. `day` counts from filing too, and is on or after the last event's.
 */
export function stillOpen(net, court, events, day) {
  const mean = new Float64Array(net.horizon);
  for (const member of net.members) {
    const one = forecast(member, court, events, day);
    for (let k = 0; k < mean.length; k++) mean[k] += one[k] / net.members.length;
  }
  return mean;
}

const sigmoid = (x) => 1 / (1 + Math.exp(-x));

// out = W x + b, for W of shape [rows, columns], stored row by row.
function affine({ shape: [rows, columns], values: w }, x, bias) {
  const out = new Float64Array(rows);
  for (let i = 0; i < rows; i++) {
    let sum = bias ? bias.values[i] : 0;
    const row = i * columns;
    for (let j = 0; j < columns; j++) sum += w[row + j] * x[j];
    out[i] = sum;
  }
  return out;
}

// The row of a matrix stored row by row.
const row = ({ shape: [, columns], values }, i) => values.subarray(i * columns, (i + 1) * columns);

/** One network's forecast. */
function forecast(m, court, events, day) {
  const size = m['gru.weight_hh_l0'].shape[1];
  let h = new Float64Array(size);
  let previous = 0;
  for (const [code, when] of events) {
    const x = [...row(m['code.weight'], code), Math.log1p(when - previous), Math.log1p(when)];
    const gi = affine(m['gru.weight_ih_l0'], x, m['gru.bias_ih_l0']);
    const gh = affine(m['gru.weight_hh_l0'], h, m['gru.bias_hh_l0']);
    const next = new Float64Array(size);
    for (let i = 0; i < size; i++) {
      const r = sigmoid(gi[i] + gh[i]);
      const z = sigmoid(gi[size + i] + gh[size + i]);
      const n = Math.tanh(gi[2 * size + i] + r * gh[2 * size + i]);
      next[i] = (1 - z) * n + z * h[i];
    }
    h = next;
    previous = when;
  }
  const x = [...h, ...row(m['court.weight'], court), Math.log1p(day - previous), Math.log1p(day)];
  const layer = affine(m['layer.weight'], x, m['layer.bias']).map((v) => Math.max(v, 0));
  const finishing = affine(m['out.weight'], layer, m['out.bias']);
  const still = new Float64Array(finishing.length);
  let open = 1;
  for (let k = 0; k < finishing.length; k++) {
    open *= 1 - sigmoid(finishing[k]);
    still[k] = open;
  }
  return still;
}

/** The chance a case ends within each number of months, from its chances of still being open. */
export const within = (still, months) => months.map((k) => 1 - still[k - 1]);
