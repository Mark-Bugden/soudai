import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { matches, normalise, searchIndex } from '../src/courts.js';

const raw = JSON.parse(readFileSync(new URL('../public/data/soudai.json', import.meta.url), 'utf8'));
const index = searchIndex(raw.courts);
const names = (query) => matches(index, query).map((court) => court.name);

test('normalises names for matching, without diacritics', () => {
  assert.equal(normalise('Děčín'), 'decin');
  assert.equal(normalise('  Okresní soud Praha-východ '), 'okresni soud praha vychod');
  assert.equal(normalise('Ústí nad Labem'), 'usti nad labem');
  assert.equal(normalise('Žďár nad Sázavou'), 'zdar nad sazavou');
});

test('an empty query lists every court, in order of area, as Czech sorts it', () => {
  const all = matches(index, '');
  assert.equal(all.length, 86);
  assert.equal(all[0].area, 'Benešov');
  const areas = all.map((court) => court.area);
  // Czech sorts "ch" after "h", and the Prague districts by number.
  assert.ok(areas.indexOf('Hradec Králové') < areas.indexOf('Chomutov'));
  assert.ok(areas.indexOf('Praha 2') < areas.indexOf('Praha 10'));
  assert.deepEqual(matches(index, '   '), all);
});

test('finds a court without its diacritics', () => {
  assert.deepEqual(names('Decin'), ['Okresní soud Děčín']);
  assert.deepEqual(names('usti nad orlici'), ['Okresní soud Ústí nad Orlicí']);
  assert.deepEqual(names('ZDAR'), ['Okresní soud Žďár nad Sázavou']);
});

test('ranks a match on the area before a match on the full name', () => {
  const prague = names('praha');
  assert.equal(prague.length, 12);
  assert.equal(prague[0], 'Obvodní soud Praha 1');
  assert.deepEqual(prague.slice(-2), ['Okresní soud Praha-východ', 'Okresní soud Praha-západ']);
  // "Brno" starts two areas, Brno-město and Brno-venkov.
  assert.deepEqual(names('brno'), ['Městský soud Brno', 'Okresní soud Brno-venkov']);
  // The start of a word in the area: "Labem" in Ústí nad Labem, before anything that merely contains it.
  assert.equal(names('labem')[0], 'Okresní soud Ústí nad Labem');
});

test('matches the court type in the full name', () => {
  assert.equal(names('obvodni').length, 10);
  assert.equal(names('městský').length, 1);
  assert.equal(names('okresni soud').length, 75);
});

test('finds nothing for a name that is not a court', () => {
  assert.deepEqual(names('Vienna'), []);
});
