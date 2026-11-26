import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { TYPES, byType } from '../src/courts.js';

const raw = JSON.parse(readFileSync(new URL('../public/data/soudai.json', import.meta.url), 'utf8'));
const groups = byType(raw.courts);
const places = (type) => groups.find((group) => group.type === type).courts.map((entry) => entry.place);

test('every court is in one type, in the order the menu lists them', () => {
  assert.deepEqual(groups.map((group) => group.type), TYPES);
  assert.deepEqual(groups.map((group) => group.courts.length), [75, 10, 1]);
  const all = groups.flatMap((group) => group.courts.map((entry) => entry.court));
  assert.equal(new Set(all).size, raw.courts.length);
  for (const { type, courts } of groups) {
    for (const { court, place } of courts) assert.equal(court.name, `${type} ${place}`);
  }
});

test('a court\'s place is its name without its type', () => {
  assert.deepEqual(places('Městský soud'), ['Brno']);
  assert.ok(places('Okresní soud').includes('Děčín'));
  assert.ok(places('Okresní soud').includes('Brno-venkov'));
  assert.ok(places('Okresní soud').includes('Ostrava'));
});

test('places are in order as Czech sorts them', () => {
  const districts = places('Okresní soud');
  assert.equal(districts[0], 'Benešov');
  // Czech sorts "ch" after "h", and the Prague districts by number.
  assert.ok(districts.indexOf('Hradec Králové') < districts.indexOf('Chomutov'));
  assert.ok(districts.indexOf('Praha-východ') < districts.indexOf('Praha-západ'));
  assert.deepEqual(places('Obvodní soud'), Array.from({ length: 10 }, (_, i) => `Praha ${i + 1}`));
});

test('a court of no known type is refused', () => {
  assert.throws(() => byType([{ name: 'Krajský soud Brno', area: 'Brno' }]), /not a court of a known type/);
});
