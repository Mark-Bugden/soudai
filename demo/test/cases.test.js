import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import {
  MOST_EVENTS, add, ending, findCases, forecast, madeUp, offered, ordered, outcome, pick, soFar, undo,
} from '../src/cases.js';
import { normalise, searchIndex } from '../src/courts.js';
import { prepare } from '../src/data.js';
import { MONTH, stillOpen } from '../src/forecast.js';
import { addDays, date, forecastLine, madeUpLine, months, next, percent } from '../src/format.js';

const raw = JSON.parse(readFileSync(new URL('../public/data/soudai.json', import.meta.url), 'utf8'));
const data = prepare(raw);
const byLabel = (court, label) => data.court(court).cases.find((item) => item.label === label);

test('every real case has its court, its number, its filing date and its events', () => {
  assert.equal(data.cases.length, raw.cases.rows.length);
  const split = new Date(`${raw.split}T00:00:00Z`);
  raw.cases.rows.forEach(([court, senate, number, year, filed, span, ended, pairs], i) => {
    const item = data.cases[i];
    assert.equal(item.court, data.courts[court]);
    assert.equal(item.label, `${senate} C ${number}/${year}`);
    assert.equal(item.filed.getTime(), addDays(split, filed).getTime());
    assert.equal(item.span, span);
    assert.equal(item.ended, ended === 1);
    assert.equal(item.events.length, pairs.length / 2);
    assert.equal(item.events[0].code.code, 'ZAHAJ_RIZ');
    assert.equal(item.events[0].day, 0);
  });
  for (const court of data.courts) assert.equal(court.cases.length, 20, court.code);
});

test('every event the real cases have is on a lane of the timeline', () => {
  for (const item of data.cases) {
    for (const event of item.events) assert.ok(event.code.lane, event.code.code);
  }
  assert.equal(data.codes.find((c) => c.code === 'ST_VEC_ODS').lane, 'closed');
  assert.equal(data.codes.find((c) => c.code === 'ST_VEC_UPR').lane, 'suspended');
});

test('a court\'s cases are in order of year, senate and number', () => {
  const court = data.court('OSSCEDC');
  const labels = ordered(court.cases, [court]).map((item) => [item.year, item.senate, item.number]);
  const sorted = [...labels].sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2]);
  assert.deepEqual(labels, sorted);
  const all = ordered(data.cases, searchIndex(data.courts).map((entry) => entry.court));
  assert.equal(all.length, data.cases.length);
  assert.equal(all[0].court.area, 'Benešov');
});

test('finds a case by its number, in whole parts first', () => {
  const cases = data.court('OSJIMJI').cases;
  for (const query of ['18 C 33/2024', '18 c 33 2024', '33/2024', '18 C 33']) {
    assert.equal(findCases(cases, query)[0].label, '18 C 33/2024', query);
  }
  // A part of the number that starts with the query, such as 33 in 333/2024, counts too.
  const found = findCases(cases, '33');
  assert.ok(found.length >= 1);
  assert.ok(found.every((item) => ` ${normalise(item.label)}`.includes(' 33')));
  assert.deepEqual(findCases(cases, 'nothing'), []);
  assert.equal(findCases(cases, '  ').length, cases.length);
});

test('picks a case at random, never the one shown when there is a choice', () => {
  const cases = data.court('OSJIMJI').cases;
  assert.equal(pick(cases, null, () => 0), cases[0]);
  assert.equal(pick(cases, cases[0], () => 0), cases[1]);
  assert.equal(pick(cases, null, () => 0.9999), cases.at(-1));
  assert.equal(pick([cases[0]], cases[0], () => 0.5), cases[0]);
  assert.equal(pick([], null), null);
});

test('a forecast reads the events up to the end of its day, and never those of the last day', () => {
  const item = byLabel('OSJIMJI', '18 C 33/2024');
  assert.deepEqual(item.events.map((e) => [e.code.code, e.day]), [
    ['ZAHAJ_RIZ', 0], ['NAR_JED', 177], ['VYD_ROZH', 177], ['ST_VEC_VYR', 177], ['ST_VEC_PUK', 238],
  ]);
  assert.equal(item.span, 238);
  assert.equal(soFar(item, 0).length, 1);
  assert.equal(soFar(item, 176).length, 1);
  assert.equal(soFar(item, 177).length, 4);
  assert.equal(soFar(item, 237).length, 4);
  const still = forecast(data, item.court, soFar(item, 177), 177);
  const rows = soFar(item, 177).map((e) => [e.code.index, e.day]);
  assert.deepEqual(still, stillOpen(data.network, item.court.index, rows, 177));
});

test('how a case ended', () => {
  const counts = { final: 0, closed: 0, open: 0 };
  for (const item of data.cases) counts[ending(item)] += 1;
  assert.equal(counts.final + counts.closed, data.cases.filter((item) => item.ended).length);
  assert.equal(counts.open, data.cases.filter((item) => !item.ended).length);
  assert.equal(ending(byLabel('OSJIMJI', '18 C 33/2024')), 'final');
  assert.ok(counts.closed > 0);
});

test('whether a case ended within a time of a forecast, as the scores count it', () => {
  const ended = { span: 238, ended: true };
  assert.equal(outcome(ended, 177, 1), 'no'); // 61 days later
  assert.equal(outcome(ended, 177, 3), 'yes');
  assert.equal(outcome(ended, 238 - 30, 1), 'yes'); // a month is 30.44 days
  assert.equal(outcome(ended, 238 - 31, 1), 'no');
  const open = { span: 400, ended: false };
  assert.equal(outcome(open, 0, 12), 'no'); // still open 12 months on
  assert.equal(outcome(open, 300, 6), 'unknown'); // its record ends 100 days on
  assert.equal(outcome(open, 400 - Math.ceil(3 * MONTH), 3), 'no');
});

test('formats chances, months and dates', () => {
  assert.equal(percent(0.004), '<1%');
  assert.equal(percent(0.005), '1%');
  assert.equal(percent(0.456), '46%');
  assert.equal(percent(0.9949), '99%');
  assert.equal(percent(0.995), '>99%');
  assert.equal(months(1), '1 month');
  assert.equal(months(12), '12 months');
  assert.equal(date(new Date('2024-06-03T00:00:00Z')), '3 June 2024');
  assert.equal(date(new Date('2024-06-03T00:00:00Z'), true), '3 Jun 2024');
});

test('says what happened next, and the status line gives the forecast', () => {
  const item = byLabel('OSJIMJI', '18 C 33/2024');
  assert.equal(next(item, 'final', 177), 'It became legally final 61 days later.');
  assert.equal(next(item, 'closed', 0), 'It was closed in the register 238 days later.');
  const open = data.cases.find((c) => !c.ended);
  assert.match(next(open, 'open', 0), /^It was still open [\d,]+ days later, on \d+ \w+ 202\d, when its record ends\.$/);
  assert.equal(
    forecastLine(item, 0, [0.01, 0.1, 0.48, 0.92], [1, 3, 6, 12], 'final'),
    '18 C 33/2024, Okresní soud Jihlava, at filing. Chance it ends: 1% within 1 month, 10% within 3 months, '
      + '48% within 6 months and 92% within 12 months. It became legally final 238 days later.',
  );
  assert.match(forecastLine(item, 177, [0.5, 0.9, 0.99, 1], [1, 3, 6, 12], 'final'), /, on 21 March 2024, day 177\. /);
});

test('with no court, a forecast is the courts\' forecasts averaged, weighted by their cases registered', () => {
  const item = byLabel('OSJIMJI', '18 C 33/2024');
  const events = soFar(item, 177);
  const mixed = forecast(data, null, events, 200);
  const expected = new Float64Array(mixed.length);
  for (const court of data.courts) {
    const one = forecast(data, court, events, 200);
    one.forEach((value, k) => { expected[k] += (value * court.journey.registered) / data.registered; });
  }
  mixed.forEach((value, k) => assert.ok(Math.abs(value - expected[k]) < 1e-12, `month ${k + 1}`));
});

test('a made-up case can have the events the network learned from, but those that end a case', () => {
  const options = offered(data);
  const codes = new Set(options.flatMap((option) => option.codes.map((code) => code.code)));
  for (const left of ['ZAHAJ_RIZ', 'ST_VEC_PUK', 'ST_VEC_ODS', 'DOVOL_RIZ', 'ZRUS_JED']) assert.ok(!codes.has(left), left);
  assert.equal(codes.size, 12);
  // Each is in the real cases' histories before their end, so the network has seen it.
  const seen = new Set(data.cases.flatMap((item) => item.events.filter((e) => e.day < item.span).map((e) => e.code.code)));
  for (const code of codes) assert.ok(seen.has(code), code);
  assert.equal(options[0].label, 'Hearing');
  assert.equal(options[1].label, 'Decision issued, and case disposed');
  assert.deepEqual(options[1].codes.map((code) => code.code), ['VYD_ROZH', 'ST_VEC_VYR']);
});

test('a made-up case gains events in order, and loses the last thing added', () => {
  const [hearing, decision] = offered(data);
  const start = madeUp(data, null);
  assert.deepEqual(start.events.map((e) => [e.code.code, e.day]), [['ZAHAJ_RIZ', 0]]);
  assert.equal(undo(start), start);
  const heard = add(start, hearing.codes, 90);
  const decided = add(heard, decision.codes, 90);
  assert.deepEqual(decided.events.map((e) => [e.code.code, e.day]),
    [['ZAHAJ_RIZ', 0], ['NAR_JED', 90], ['VYD_ROZH', 90], ['ST_VEC_VYR', 90]]);
  assert.equal(add(decided, hearing.codes, 89), decided); // before its last event
  assert.deepEqual(undo(decided).events, heard.events); // both of the decision's events
  assert.deepEqual(undo(undo(decided)).events, start.events);
  assert.equal(soFar(decided, 90).length, 4);
  let full = start;
  for (let i = 1; i < MOST_EVENTS; i++) full = add(full, hearing.codes, i);
  assert.equal(full.events.length, MOST_EVENTS);
  assert.equal(add(full, hearing.codes, 100), full);
});

test('the status line for a made-up case gives its court, the day, the chances and its last event', () => {
  const [hearing] = offered(data);
  const start = madeUp(data, null);
  assert.equal(madeUpLine(start, 0, [0.01, 0.1, 0.5, 0.9], [1, 3, 6, 12]),
    'Made-up case, all courts, at filing. Chance it ends: 1% within 1 month, 10% within 3 months, '
      + '50% within 6 months and 90% within 12 months.');
  const heard = { ...add(start, hearing.codes, 150), court: data.court('OSSCEDC') };
  assert.match(madeUpLine(heard, 170, [0.05, 0.3, 0.5, 0.7], [1, 3, 6, 12]),
    /^Made-up case, Okresní soud Děčín, on day 170\. Chance it ends: .*\. Its last event: Hearing, on day 150\.$/);
});
