import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { prepare } from '../src/data.js';
import { moveLabel, notDrawn, route, share, wait } from '../src/format.js';
import { DRAWN, PLACES, commonest, legallyFinal, moves, shape, split } from '../src/journey.js';
import { arc, line, place } from '../src/views/map.js';

const raw = JSON.parse(readFileSync(new URL('../public/data/soudai.json', import.meta.url), 'utf8'));
const data = prepare(raw);
const find = (list, from, to) => list.find((move) => move.from === from && move.to === to);

test('every stage has a place on the map', () => {
  assert.deepEqual(Object.keys(PLACES).sort(), [...data.stages].sort());
  for (const [x, y] of Object.values(PLACES)) assert.ok(x >= 0 && x <= 1 && y >= 0 && y <= 1);
});

test('the moves, from the commonest, with their waits', () => {
  for (const scope of [null, ...data.courts]) {
    const list = moves(data.journey(scope), data.stages);
    assert.equal(list.length, data.journey(scope).moves.length);
    list.forEach((move, i) => {
      assert.ok(data.stages.includes(move.from) && data.stages.includes(move.to));
      assert.notEqual(move.from, 'final');
      assert.ok(move.share > 0 && move.share <= 1);
      if (i) assert.ok(move.share <= list[i - 1].share);
      if (move.wait) assert.ok(move.wait[0] <= move.wait[1] && move.wait[1] <= move.wait[2]);
    });
    // Becoming legally final after a decision is the commonest move everywhere.
    assert.deepEqual([list[0].from, list[0].to], ['decided', 'final'], scope?.code);
  }
  const all = moves(data.journey(null), data.stages);
  assert.deepEqual(find(all, 'decided', 'final').wait, [19, 30, 42]);
  assert.deepEqual(find(all, 'hearing', 'decided').wait, [0, 0, 0]);
  assert.equal(find(all, 'suspended', 'closed').wait, null); // made by one sampled case
});

test('the commonest route', () => {
  const all = commonest(data.journey(null), data.stages);
  assert.deepEqual(all.stages, ['filed', 'hearing', 'decided', 'final']);
  assert.equal(all.ending, 'final');
  assert.equal(all.share, 0.7182);
  // Hradec Králové records a hearing in few cases.
  assert.deepEqual(commonest(data.journey(data.court('OSVYCHK')), data.stages).stages, ['filed', 'decided', 'final']);
});

test('the map draws moves of at least 2% between stages next to each other, and lists the rest', () => {
  const all = moves(data.journey(null), data.stages);
  const { drawn, rest } = split(all);
  assert.deepEqual(drawn.map((m) => `${m.from} ${m.to}`), [
    'decided final', 'hearing decided', 'filed hearing', 'filed decided', 'decided appeal', 'appeal final',
    'revived hearing', 'decided revived', 'filed suspended',
  ]);
  assert.equal(drawn.length + rest.length, all.length);
  assert.ok(rest.every((m) => m.share < DRAWN || !shape(m.from, m.to)));
  // Filing to an appeal would cross the hearing and the decision, so it's listed however common.
  assert.equal(shape('filed', 'appeal'), null);
  assert.equal(shape('filed', 'decided'), 'arc');
  assert.equal(shape('appeal', 'decided'), 'line');
  assert.equal(shape('decided', 'appeal'), 'line');
  for (const court of data.courts) {
    for (const m of split(moves(data.journey(court), data.stages)).drawn) assert.ok(shape(m.from, m.to), court.code);
  }
  const lead = 'Not drawn, as under 2% of cases or crossing a stage: ';
  assert.equal(notDrawn(rest), `${lead}appeal → revived (1.7%), filed → appeal (1.3%), suspended → decided (1.2%) and ${rest.length - 3} more.`);
  assert.equal(notDrawn(rest.slice(0, 2)), `${lead}appeal → revived (1.7%) and filed → appeal (1.3%).`);
  assert.equal(notDrawn([]), '');
  assert.deepEqual(moveLabel(drawn[2]), ['76.1%', '147 days']);
  assert.deepEqual(moveLabel({ share: 0.03, wait: null }), ['3.0%']);
});

test('the share legally final, month by month', () => {
  const all = data.journey(null);
  const final = legallyFinal(all);
  assert.equal(final[0], 0);
  assert.equal(final[12], 1 - all.notFinal[12]);
  for (let m = 1; m < final.length; m++) assert.ok(final[m] >= final[m - 1]);
});

test('arrows start and end clear of their stages, and a move and its reverse sit side by side', () => {
  const ahead = line([0, 0], [100, 0], 4, 6);
  const back = line([100, 0], [0, 0], 4, 6);
  assert.ok(ahead.at(0.5)[1] < 0 && back.at(0.5)[1] > 0, 'each to the left of its travel');
  assert.deepEqual(ahead.left(0.5), [0, -1]);
  const [, sx] = ahead.path.match(/^M([-\d.]+),([-\d.]+)/).map(Number);
  assert.equal(sx, 10);
  const [, tx] = ahead.head.match(/^M([-\d.]+),([-\d.]+)/).map(Number);
  assert.equal(tx, 90);
  // The arc rises to its lift at its middle, and its ends point away from and into the stages.
  const over = arc([0, 100], [200, 100], 6, 60);
  const [mx, my] = over.at(0.5);
  assert.ok(Math.abs(mx - 100) < 5, 'near the middle: the line stops at the base of its head');
  assert.ok(my < 100 - 55 && my > 100 - 65, 'about its lift above the row');
  assert.ok(over.left(0.5)[1] < -0.99, 'its left is up at the top');
  assert.ok(over.samples.every(([, y]) => y <= 100));
});

test('a label goes beside its arrow, clear of what is already placed', () => {
  const space = { width: 400, height: 300, taken: [], marks: [], measure: (text) => text.length * 6.6 };
  const flat = line([50, 150], [350, 150], 4);
  const below = place(['76.1%', '147 days'], 4, flat, space);
  assert.deepEqual(below.lines, ['76.1% · 147 days']);
  assert.ok(below.bounds[1] > 150 + 2, 'under the line, the right of its travel');
  const above = place(['76.1%', '147 days'], 4, flat, { ...space, taken: [below.bounds] });
  assert.ok(above.bounds[3] < 150 - 2);
  assert.ok(place(['3.2%', '78 days'], 4, flat, space, { sides: [1, -1] }).bounds[3] < 150, 'the left first, when asked');
  // Set into its own arrow, but not into another's.
  const owner = {};
  const marks = flat.samples.map(([x, y]) => [x, y, 4, owner]);
  const on = place(['3.2%', '78 days'], 4, flat, { ...space, marks }, { on: true, owner });
  assert.ok(on.on && on.bounds[1] < 150 && on.bounds[3] > 150);
  const other = place(['3.2%', '78 days'], 4, flat, { ...space, marks }, { on: true, owner: {} });
  assert.ok(!other.on && other.bounds[1] > 150);
});

test('the map\'s text', () => {
  assert.equal(wait(0), 'same day');
  assert.equal(wait(1), '1 day');
  assert.equal(wait(147), '147 days');
  assert.equal(route(['filed', 'hearing', 'decided', 'final']), 'filed → hearing → decided → legally final');
  assert.equal(share(0.9325), '93.3%');
  assert.equal(share(0.0002), '<0.1%');
});
