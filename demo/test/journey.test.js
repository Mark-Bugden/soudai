import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { prepare } from '../src/data.js';
import { moveLabel, notShown, route, routeText, share, wait } from '../src/format.js';
import { ARCS, DRAWN, LISTED, PLACES, commonest, legallyFinal, mostCommon, moves, routes, shape, split } from '../src/journey.js';
import { stack } from '../src/reading.js';
import { arrow, nearer, place, route as curve } from '../src/views/map.js';

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

test('the commonest routes', () => {
  const list = routes(data.journey(null), data.stages);
  list.forEach((r, i) => i && assert.ok(r.share <= list[i - 1].share));
  assert.equal(routeText(list[0]), 'filed → hearing → decided → legally final');
  assert.equal(routeText({ stages: ['filed', 'decided'], ending: 'closed' }), 'filed → decided → closed');
  assert.equal(routeText({ stages: ['filed', 'suspended'], ending: 'open' }), 'filed → suspended, still open');
});

test('the most common routes: those over 5%, then all the others together', () => {
  const all = mostCommon(data.journey(null), data.stages);
  assert.deepEqual(all.list.map(routeText), ['filed → hearing → decided → legally final', 'filed → decided → legally final']);
  assert.ok(Math.abs(all.others - (1 - 0.7182 - all.list[1].share)) < 1e-9);
  for (const court of data.courts) {
    const { list, others } = mostCommon(data.journey(court), data.stages);
    assert.ok(list.length >= 1 && list.every((r) => r.share > LISTED), court.code);
    assert.ok(others > 0 && others < 1, court.code);
  }
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
  assert.equal(shape('filed', 'decided'), 'over');
  assert.equal(shape('appeal', 'decided'), 'under');
  assert.equal(shape('revived', 'hearing'), 'under');
  assert.equal(shape('appeal', 'revived'), 'line');
  assert.equal(shape('filed', 'suspended'), 'under');
  assert.equal(shape('suspended', 'hearing'), 'under');
  assert.equal(shape('appeal', 'hearing'), null);
  for (const court of data.courts) {
    for (const m of split(moves(data.journey(court), data.stages)).drawn) assert.ok(shape(m.from, m.to), court.code);
  }
  assert.equal(notShown(rest, DRAWN), 'Not shown: paths followed by less than 2% of cases.');
  assert.equal(notShown([], DRAWN), '');
  // At a court where a move of 2% or more would cross another stage, it's named.
  const deep = { from: 'filed', to: 'appeal', share: 0.025 };
  assert.equal(notShown([deep, ...rest], DRAWN),
    'Not shown: paths followed by less than 2% of cases, and those that would cross another stage: filed → appeal (2.5%).');
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

// Stages on a map 300 wide, with the top row at y = 100 and the bottom row 60 below it.
const at = (stage) => [PLACES[stage][0] * 300, 100 + PLACES[stage][1] * 60];
const near = (a, b) => Math.abs(a[0] - b[0]) < 1e-9 && Math.abs(a[1] - b[1]) < 1e-9;

test('the arcs below the row pass through suspensions, revivals and appeals', () => {
  // The arc from the hearing to a decision has its bottom at the revival.
  assert.deepEqual(Object.keys(ARCS).sort(), ['appeal', 'revived', 'suspended']);
  for (const [bottom, [left, right]] of Object.entries(ARCS)) {
    assert.ok(Math.abs(at(bottom)[0] - (at(left)[0] + at(right)[0]) / 2) < 1e-9, bottom);
    const down = curve(left, bottom, at);
    const up = curve(bottom, right, at);
    assert.ok(near(down[0], at(left)) && near(down[3], at(bottom)), `${left} to ${bottom}`);
    assert.ok(near(up[0], at(bottom)) && near(up[3], at(right)), `${bottom} to ${right}`);
    // Mirror images, each reaching the bottom from above at the same slope, so a line along the bottom
    // row leaves it clear of them.
    const slope = (a, b) => (b[1] - a[1]) / (b[0] - a[0]);
    assert.ok(slope(down[2], down[3]) > 0.3 && Math.abs(slope(down[2], down[3]) + slope(up[0], up[1])) < 1e-9);
    // A move back up the same half is the same curve the other way.
    assert.deepEqual(curve(bottom, left, at), [...down].reverse());
  }
  // The arc over the hearing's arrow rises as far above the row at its middle as the arcs below dip
  // under it, whatever its width.
  for (const width of [1, 24]) assert.ok(Math.abs(arrow(curve('filed', 'decided', at), width).at(0.5)[1] - (100 - 60)) < 1e-6);
});

test('arrows start and end clear of their stages, and a move and its reverse sit side by side', () => {
  const straight = curve('filed', 'hearing', at);
  const ahead = arrow(straight, 4, 6);
  const back = arrow([...straight].reverse(), 4, 6);
  assert.ok(ahead.at(0.5)[1] < 100 && back.at(0.5)[1] > 100, 'each to the left of its travel');
  assert.deepEqual(ahead.left(0.5), [0, -1]);
  const plain = arrow(straight, 4);
  const [, sx] = plain.path.match(/^M([-\d.]+),([-\d.]+)/).map(Number);
  assert.equal(sx, 10);
  const [, tx] = plain.head.match(/^M([-\d.]+),([-\d.]+)/).map(Number);
  assert.equal(tx, at('hearing')[0] - 10);
  // A curve's ends point along it: the drop to a revival leaves the decision downwards.
  const dip = arrow(curve('decided', 'revived', at), 4);
  const [x0, y0] = dip.at(0);
  assert.ok(y0 > 100 && Math.hypot(x0 - at('decided')[0], y0 - 100) > 9.9);
});

test('an arrow\'s share goes on one side and its wait on the other, clear of what is placed', () => {
  const measure = (text) => text.length * 6.6;
  const space = { width: 400, height: 300, taken: [], marks: [], measure };
  const flat = arrow([[50, 150], [150, 150], [250, 150], [350, 150]], 4);
  const [share, days] = place(['76.1%', '147 days'], 4, flat, space);
  assert.deepEqual([share.lines, days.lines], [['76.1%'], ['147 days']]);
  assert.ok(share.bounds[3] < 150 && days.bounds[1] > 150, 'the share above, the wait below');
  // Upright, the share goes on the left.
  const drop = arrow([[100, 50], [100, 100], [100, 150], [100, 250]], 4);
  const [left, right] = place(['2.3%', '151 days'], 4, drop, space);
  assert.ok(left.bounds[2] < 100 && right.bounds[0] > 100);
  // With the space above taken, both go below; beside a move's reverse, both go on its outside.
  const below = place(['76.1%', '147 days'], 4, flat, { ...space, taken: [[0, 0, 400, 148]] });
  assert.equal(below.length, 1);
  assert.ok(below[0].bounds[1] > 150);
  const together = place(['4.4%', '97 days'], 4, flat, space, { together: true });
  assert.equal(together.length, 1);
  assert.deepEqual(together[0].lines, ['4.4%', '97 days']);
  assert.deepEqual(place(['3.0%'], 4, flat, space).map((b) => b.lines), [['3.0%']]);
  // On a diagonal arrow, steep at one end and flat at the other, they sit across it where it runs at
  // about 45°, so the line between them is at about 45° too.
  const bend = arrow([[100, 40], [100, 140], [150, 240], [250, 240]], 2);
  const [one, two] = place(['2.3%', '151 days'], 2, bend, space);
  const centre = (box) => [box.x, (box.bounds[1] + box.bounds[3]) / 2];
  const [[x1, y1], [x2, y2]] = [centre(one), centre(two)];
  assert.ok(Math.abs((Math.atan2(Math.abs(y2 - y1), Math.abs(x2 - x1)) * 180) / Math.PI - 45) < 15);
});

test('labels shown all the time are plainly their arrow\'s; the rest wait for a hover', () => {
  const measure = (text) => text.length * 6.6;
  const flat = arrow([[50, 150], [150, 150], [250, 150], [350, 150]], 4);
  const marks = (geometry, w, id) => geometry.samples.map(([x, y]) => [x, y, w / 2 + 2, id]);
  // Another thin arrow 30 px above and below: too close for a label beside a hairline.
  const above = arrow([[50, 120], [150, 120], [250, 120], [350, 120]], 2);
  const below = arrow([[50, 180], [150, 180], [250, 180], [350, 180]], 2);
  const crowded = { width: 400, height: 300, taken: [], measure, own: 0,
    marks: [...marks(flat, 2, 0), ...marks(above, 2, 1), ...marks(below, 2, 2)] };
  assert.deepEqual(place(['2.7%', '62 days'], 2, flat, crowded), []);
  // On hover, it doesn't need to be.
  assert.equal(place(['2.7%', '62 days'], 2, flat, crowded, { sure: false }).length, 2);
  // A thick arrow claims its labels more plainly: with another arrow 50 px above, a label just above a
  // hairline isn't plainly its own, but one just above an arrow 16 px wide is.
  const higher = arrow([[50, 100], [150, 100], [250, 100], [350, 100]], 2);
  const box = [180, 128, 220, 140];
  assert.equal(nearer(box, [...marks(flat, 2, 0), ...marks(higher, 2, 1)], 0), false);
  assert.equal(nearer(box, [...marks(flat, 16, 0), ...marks(higher, 2, 1)], 0), true);
  // The arrow's reverse doesn't count.
  assert.equal(nearer(box, [...marks(flat, 2, 0), ...marks(higher, 2, 1)], 0, 1), true);
});

test('values read off the curve are moved apart until they can be read', () => {
  assert.deepEqual(stack([100, 50], 15), [100, 50]);
  assert.deepEqual(stack([100, 95], 15), [105, 90]);
  assert.deepEqual(stack([40], 15), [40]);
});

test('the map\'s text', () => {
  assert.equal(wait(0), 'same day');
  assert.equal(wait(1), '1 day');
  assert.equal(wait(147), '147 days');
  assert.equal(route(['filed', 'hearing', 'decided', 'final']), 'filed → hearing → decided → legally final');
  assert.equal(share(0.9325), '93.3%');
  assert.equal(share(0.0002), '<0.1%');
});
