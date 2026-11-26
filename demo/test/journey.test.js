import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { prepare } from '../src/data.js';
import { route, share, wait } from '../src/format.js';
import { PLACES, commonest, moves, waiting } from '../src/journey.js';
import { arrow } from '../src/views/map.js';

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

test('the share still waiting, month by month', () => {
  const all = data.journey(null);
  assert.deepEqual(waiting(all, 0), { decided: 1, final: 1 });
  assert.deepEqual(waiting(all, 12), { decided: all.notDecided[12], final: all.notFinal[12] });
  assert.ok(waiting(all, 6).decided < waiting(all, 6).final);
});

test('an arrow bows to its left, so a move and its reverse don\'t overlap', () => {
  const right = arrow([0, 0], [100, 0], 4);
  const left = arrow([100, 0], [0, 0], 4);
  assert.ok(right.label[1] < 0, 'rightwards bows up');
  assert.ok(left.label[1] > 0, 'leftwards bows down');
  // It starts clear of the stage it leaves, and its head ends clear of the stage it reaches.
  const [, sx, sy] = right.path.match(/^M([-\d.]+),([-\d.]+)/).map(Number);
  assert.ok(Math.hypot(sx, sy) >= 9.9);
  const [, tx, ty] = right.head.match(/^M([-\d.]+),([-\d.]+)/).map(Number);
  assert.ok(Math.hypot(tx - 100, ty) >= 9.9 && Math.hypot(tx - 100, ty) < 11);
});

test('the map\'s text', () => {
  assert.equal(wait(0), 'same day');
  assert.equal(wait(1), '1 day');
  assert.equal(wait(147), '147 days');
  assert.equal(route(['filed', 'hearing', 'decided', 'final']), 'filed → hearing → decided → legally final');
  assert.equal(share(0.9325), '93.3%');
  assert.equal(share(0.0002), '<0.1%');
});
