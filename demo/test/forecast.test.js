import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { decode, fullNetwork, network, stillOpen, within } from '../src/forecast.js';

const read = (path) => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'));
// The Python reference's fixture: two networks with random weights, and PyTorch's forecasts with them.
const fixture = read('../../tests/fixtures/network/forward.json');
// The trained ensemble in full, and as the demo carries it, in 16 bits.
const weights = read('../../data/derived/network.json');
const data = read('../public/data/soudai.json');

const rows = (codes) => new Map(codes.map((code, i) => [code, i]));

test('the forward pass gives PyTorch\'s forecasts', () => {
  const net = fullNetwork(fixture.weights);
  const codes = rows(fixture.weights.codes);
  const courts = rows(fixture.weights.courts);
  assert.equal(fixture.forecasts.length, 27);
  let gap = 0;
  for (const { court, events, day, still_open: expected } of fixture.forecasts) {
    const got = stillOpen(net, courts.get(court), events.map(([code, when]) => [codes.get(code), when]), day);
    assert.equal(got.length, expected.length);
    expected.forEach((value, k) => { gap = Math.max(gap, Math.abs(got[k] - value)); });
  }
  // numpy matches PyTorch to 1.7e-8 on this fixture: the gap is PyTorch's 32-bit arithmetic.
  assert.ok(gap < 1e-7, `largest gap ${gap}`);
});

test('the exported weights decode to the trained weights, to within half a step', () => {
  assert.equal(data.network.members.length, weights.members.length);
  data.network.members.forEach((member, i) => {
    for (const [name, encoded] of Object.entries(member)) {
      const full = weights.members[i][name];
      const { shape, values } = decode(encoded);
      assert.deepEqual(shape, Array.isArray(full[0]) ? [full.length, full[0].length] : [full.length], name);
      const flat = full.flat();
      assert.equal(values.length, flat.length, name);
      flat.forEach((value, j) => assert.ok(Math.abs(values[j] - value) <= encoded.scale / 2 + 1e-12, `${name}[${j}]`));
    }
  });
});

test('the courts and event codes are in the network\'s order', () => {
  assert.deepEqual(data.courts.map((c) => c.code), weights.courts);
  assert.deepEqual(data.codes.map((c) => c.code), weights.codes);
});

test('the exported network forecasts the real cases as the full one does', () => {
  const full = fullNetwork(weights);
  const exported = network(data.network);
  let gap = 0;
  for (const [court, , , , , span, , pairs] of data.cases.rows.slice(0, 40)) {
    const history = [];
    for (let i = 0; i < pairs.length; i += 2) history.push([pairs[i], pairs[i + 1]]);
    for (const day of new Set(history.map(([, when]) => when).filter((when) => when < span))) {
      const soFar = history.filter(([, when]) => when <= day);
      const a = stillOpen(full, court, soFar, day);
      const b = stillOpen(exported, court, soFar, day);
      a.forEach((value, k) => { gap = Math.max(gap, Math.abs(value - b[k])); });
    }
  }
  assert.ok(gap < 1e-4, `largest gap ${gap}`);
});

test('forecasts are chances, falling month by month', () => {
  const net = network(data.network);
  const still = stillOpen(net, 0, [[data.codes.findIndex((c) => c.code === 'ZAHAJ_RIZ'), 0]], 0);
  assert.equal(still.length, 36);
  still.forEach((value, k) => {
    assert.ok(value > 0 && value < 1);
    if (k) assert.ok(value <= still[k - 1]);
  });
  assert.deepEqual(within(still, [1, 3]), [1 - still[0], 1 - still[2]]);
});

test('several courts with weights give their forecasts\' weighted mean', () => {
  const net = network(data.network);
  const events = [[data.codes.findIndex((c) => c.code === 'ZAHAJ_RIZ'), 0], [data.codes.findIndex((c) => c.code === 'NAR_JED'), 40]];
  const a = stillOpen(net, 3, events, 60);
  const b = stillOpen(net, 50, events, 60);
  const mixed = stillOpen(net, [[3, 0.25], [50, 0.75]], events, 60);
  mixed.forEach((value, k) => assert.ok(Math.abs(value - (0.25 * a[k] + 0.75 * b[k])) < 1e-12));
  assert.deepEqual(stillOpen(net, [[3, 1]], events, 60), a);
});
