import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { prepare } from '../src/data.js';
import { list, performanceLine, points } from '../src/format.js';
import { BINS, LANDMARKS, METHODS, MODEL, calibration, counts, gap, ranking } from '../src/performance.js';

const raw = JSON.parse(readFileSync(new URL('../public/data/soudai.json', import.meta.url), 'utf8'));
const data = prepare(raw);

test('every method compared has its ranking at every landmark', () => {
  const lines = ranking(data);
  assert.deepEqual(lines.map((line) => line.key), METHODS.map((method) => method.key));
  assert.equal(lines.at(-1).key, MODEL);
  for (const line of lines) {
    assert.equal(line.values.length, LANDMARKS.length);
    for (const value of line.values) assert.ok(value > 0.5 && value < 0.8, `${line.name}: ${value}`);
  }
  // At filing a case has only its court, so every method but Cox ranks about the same; later on, the
  // model ranks far better than the court average.
  const [average, , , model] = lines;
  assert.ok(Math.abs(model.values[0] - average.values[0]) < 0.005);
  assert.ok(model.values.at(-1) - average.values.at(-1) > 0.15);
});

test('the calibration bands, and their mean gap from the diagonal', () => {
  for (const horizon of data.horizons) {
    const bands = calibration(data, MODEL, horizon);
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
    assert.ok(Math.abs(gap(data, MODEL, horizon) - off / total) < 0.0005, `within ${horizon} months`);
  }
});

test('the forecasts scored, and the status line', () => {
  const { forecasts, cases } = counts(data);
  assert.equal(forecasts, 234784);
  assert.equal(cases, 69336);
  assert.equal(points(0.02498), '2.5 points');
  assert.equal(list([1, 3, 6, 12]), '1, 3, 6 and 12');
  assert.equal(
    performanceLine({ forecasts, cases, horizon: 6, gap: gap(data, MODEL, 6), ranking: ranking(data).at(-1).values }),
    'How well the model does: 234,784 forecasts for 69,336 cases registered in 2024–2025. Calibration within 6 months: '
    + 'its bands of forecasts are 2.5 points from what happened, on average. It puts two cases in the order they ended '
    + '61.0% of the time at filing, and 75.7% 12 months after.',
  );
});
