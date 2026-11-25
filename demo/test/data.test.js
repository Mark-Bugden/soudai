import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { prepare } from '../src/data.js';
import { count, days, headline } from '../src/format.js';

const raw = JSON.parse(readFileSync(new URL('../public/data/soudai.json', import.meta.url), 'utf8'));
const data = prepare(raw);

test('every court has its row in the network and its journey', () => {
  assert.equal(data.courts.length, 86);
  data.courts.forEach((court, i) => {
    assert.equal(court.index, i);
    assert.equal(court.journey, raw.journey[court.code]);
    assert.equal(data.court(court.code), court);
  });
  assert.equal(data.court('NOPE'), null);
});

test('the journey of no court is the whole country\'s', () => {
  assert.equal(data.journey(null), raw.journey.all);
  const total = data.courts.reduce((sum, court) => sum + data.journey(court).registered, 0);
  assert.equal(total, data.journey(null).registered);
});

test('formats counts and days', () => {
  assert.equal(count(1725672), '1,725,672');
  assert.equal(days(1), '1 day');
  assert.equal(days(149), '149 days');
});

test('the status line names what is selected, with its headline numbers', () => {
  assert.equal(
    headline(null, data.journey(null), 86),
    'All 86 courts: 1,725,672 cases registered in 2020–2025. Median time from filing to a decision 149 days, '
      + 'and to legally final 184 days.',
  );
  const decin = data.court('OSSCEDC');
  const line = headline(decin, data.journey(decin), 86);
  assert.match(line, /^Okresní soud Děčín: [\d,]+ cases registered in 2020–2025\. Median time from filing to a decision \d+ days, and to legally final \d+ days\.$/);
});

test('every court has the medians the status line shows', () => {
  for (const court of data.courts) {
    const { decided, final } = data.journey(court);
    assert.ok(Number.isInteger(decided[1]) && Number.isInteger(final[1]), court.code);
    assert.ok(decided[1] <= final[1], court.code);
  }
});
