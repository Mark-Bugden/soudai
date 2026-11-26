import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { prepare } from '../src/data.js';
import { list, performanceLine, points } from '../src/format.js';
import { BINS, LANDMARKS, METHODS, MODEL, calibration, counts, gap, ranking } from '../src/performance.js';
import { stack } from '../src/views/performance.js';

const raw = JSON.parse(readFileSync(new URL('../public/data/soudai.json', import.meta.url), 'utf8'));
const data = prepare(raw);

test('every method is described, and ranked at every landmark', () => {
  const scored = new Set(data.scores.rows.map((row) => row[data.scores.columns.indexOf('model')]));
  assert.deepEqual(new Set(METHODS.map((method) => method.key)), scored);
  for (const method of METHODS) assert.ok(method.name && method.about.endsWith('.'));

  // The court average, the process map, the trees and the model, and the method picked if it isn't one.
  const base = ['court average', 'process map', 'trees', MODEL];
  for (const method of METHODS) {
    const lines = ranking(data, method.key);
    const keys = base.includes(method.key) ? base : ['court average', 'process map', 'trees', method.key, MODEL];
    assert.deepEqual(lines.map((line) => line.key), keys);
    for (const line of lines) {
      assert.equal(line.values.length, LANDMARKS.length);
      for (const value of line.values) assert.ok(value > 0.5 && value < 0.8, `${line.name}: ${value}`);
    }
  }
  const lines = ranking(data);
  assert.equal(lines.length, 4);
  // At filing a case has only its court, so every method but Cox ranks about the same; later on, the
  // model ranks far better than the court average.
  const [average, , , model] = lines;
  assert.ok(Math.abs(model.values[0] - average.values[0]) < 0.005);
  assert.ok(model.values.at(-1) - average.values.at(-1) > 0.15);
});

test('every method\'s calibration bands, and their mean gap from the diagonal', () => {
  for (const { key } of METHODS) for (const horizon of data.horizons) {
    const bands = calibration(data, key, horizon);
    assert.ok(bands.length > 0 && bands.length <= BINS);
    let total = 0;
    let off = 0;
    bands.forEach((band, i) => {
      if (i) assert.ok(band.bin > bands[i - 1].bin);
      // A band's mean forecast lies within it.
      assert.ok(band.forecast >= band.bin / BINS - 1e-4 && band.forecast <= (band.bin + 1) / BINS + 1e-4);
      assert.ok(band.observed >= 0 && band.observed <= 1);
      total += band.share;
      off += band.share * Math.abs(band.forecast - band.observed);
    });
    assert.ok(Math.abs(total - 1) < 0.002);
    // The export's mean gap is the bands' distance from the diagonal, weighted by their forecasts.
    assert.ok(Math.abs(gap(data, key, horizon) - off / total) < 0.0005, `${key} within ${horizon} months`);
  }
});

test('crowded names at the ends of the lines come apart, in order', () => {
  // Five names within 6 px, as at a short stage, and one far off.
  const wanted = [40, 43, 41, 44, 46, 120];
  const placed = stack(wanted, 15);
  const order = wanted.map((at, i) => i).sort((a, b) => wanted[a] - wanted[b]);
  for (let k = 1; k < order.length; k++) {
    assert.ok(placed[order[k]] - placed[order[k - 1]] >= 15 - 1e-9);
  }
  // The crowded five are centred where they wanted to be, on average; the one far off stays put.
  const mean = (list) => list.reduce((sum, v) => sum + v, 0) / list.length;
  assert.ok(Math.abs(mean(placed.slice(0, 5)) - mean(wanted.slice(0, 5))) < 1e-9);
  assert.equal(placed[5], 120);
  // Names already apart don't move.
  assert.deepEqual(stack([10, 50, 30], 15), [10, 50, 30]);
});

test('the forecasts scored, and the status line', () => {
  const { forecasts, cases } = counts(data);
  assert.equal(forecasts, 234784);
  assert.equal(cases, 69336);
  assert.equal(points(0.02498), '2.5 points');
  assert.equal(list([1, 3, 6, 12]), '1, 3, 6 and 12');
  assert.equal(
    performanceLine({ forecasts, cases, horizon: 6, name: 'This model', gap: gap(data, MODEL, 6), ranking: ranking(data).at(-1).values }),
    'How well the model does: 234,784 forecasts for 69,336 cases registered in 2024–2025. This model: calibration within '
    + '6 months, its bands of forecasts are 2.5 points from what happened, on average. It puts two cases in the order '
    + 'they ended 61.0% of the time at filing, and 75.7% 12 months after.',
  );
});
