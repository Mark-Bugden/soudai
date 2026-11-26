import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { prepare } from '../src/data.js';
import { landmark, score, scoresLine } from '../src/format.js';
import { LANDMARKS, MODEL, MODELS, best, calibration, scoreTable } from '../src/scores.js';

const raw = JSON.parse(readFileSync(new URL('../public/data/soudai.json', import.meta.url), 'utf8'));
const data = prepare(raw);
const exported = (model, court, when) => {
  const { columns, rows } = raw.scores;
  const row = rows.find((r) => r[0] === model && r[1] === court && r[2] === when);
  return Object.fromEntries(columns.map((name, i) => [name, row[i]]));
};

test('every method the export scores is shown, from the simplest to the model', () => {
  assert.deepEqual(new Set(MODELS.map((m) => m.key)), new Set(raw.scores.rows.map((row) => row[0])));
  assert.equal(MODELS.at(-1).key, MODEL);
  for (const model of MODELS) assert.ok(model.name && model.about, model.key);
});

test('the scores for all courts, at each landmark', () => {
  for (const when of LANDMARKS) {
    const table = scoreTable(data, null, when);
    assert.deepEqual(table.rows.map((row) => row.key), MODELS.map((m) => m.key));
    for (const row of table.rows) {
      const want = exported(row.key, 'all', when);
      assert.equal(row.concordance, want.concordance);
      for (const h of data.horizons) {
        assert.equal(row.brier[h], want[`brier_${h}`]);
        assert.equal(row.calibration[h], want[`calibration_${h}`]);
      }
    }
    assert.equal(table.forecasts, exported(MODEL, 'all', when).cuts);
  }
  assert.equal(scoreTable(data, null).forecasts, 234784);
  assert.equal(scoreTable(data, null, '0').forecasts, 69336);
});

test('a court\'s scores are for all its forecasts together, whatever the landmark', () => {
  for (const court of data.courts) {
    const table = scoreTable(data, court, '6');
    assert.equal(table.forecasts, exported(MODEL, court.code, 'all').cuts, court.code);
    assert.equal(table.rows.find((row) => row.key === MODEL).concordance, exported(MODEL, court.code, 'all').concordance);
  }
  // Within one court, the court average gives every case at a landmark the same forecast: a coin toss.
  const decin = scoreTable(data, data.court('OSSCEDC'));
  assert.equal(decin.rows[0].concordance, 0.5);
});

test('the best methods, with a tie at 3 decimal places counted as a tie', () => {
  const rows = scoreTable(data, null).rows;
  assert.deepEqual(best(rows, (row) => row.concordance).map((row) => row.key), [MODEL]);
  // Within 6 months the trees (0.1887) and the network (0.1890) both show 0.189.
  assert.deepEqual(best(rows, (row) => row.brier[6], { lower: true }).map((row) => row.key), ['trees', MODEL]);
  assert.deepEqual(best(rows, (row) => row.brier[6], { lower: true, digits: 4 }).map((row) => row.key), ['trees']);
  assert.deepEqual(best(rows, (row) => row.brier[1], { lower: true }).map((row) => row.key), [MODEL]);
});

test('a method\'s calibration, by band of 10 points', () => {
  for (const model of MODELS) {
    for (const h of data.horizons) {
      const points = calibration(data, model.key, h);
      assert.ok(points.length >= 3 && points.length <= 10, `${model.key} ${h}`);
      assert.deepEqual(points.map((p) => p.bin), [...points.map((p) => p.bin)].sort((a, b) => a - b));
      const total = points.reduce((sum, p) => sum + p.share, 0);
      assert.ok(Math.abs(total - 1) < 0.002, `${model.key} ${h}: ${total}`);
      for (const p of points) {
        assert.ok(p.forecast >= p.bin / 10 - 1e-9 && p.forecast <= (p.bin + 1) / 10 + 1e-9, `${model.key} ${h} ${p.bin}`);
        assert.ok(p.observed >= 0 && p.observed <= 1);
      }
    }
  }
});

test('the scores\' text', () => {
  assert.equal(score(0.6472), '0.647');
  assert.equal(score(0.0878), '0.088');
  assert.equal(landmark('0'), 'made at filing');
  assert.equal(landmark('3'), 'made 3 months after filing');
  const rows = scoreTable(data, null).rows;
  const line = scoresLine(null, 'all', 234784, best(rows, (r) => r.concordance), best(rows, (r) => r.brier[6], { lower: true }), 6);
  assert.equal(line, 'All courts: 234,784 forecasts on cases registered in 2024–2025. Best at ranking: GRU network (0.647). '
    + 'Lowest error within 6 months: Boosted trees and GRU network (0.189).');
  const at = scoresLine(null, '1', 68576, best(rows, (r) => r.concordance), best(rows, (r) => r.brier[1], { lower: true }), 1);
  assert.match(at, /^All courts: 68,576 forecasts on cases registered in 2024–2025, made 1 month after filing\. /);
});
