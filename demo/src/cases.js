// The cases the Forecast tab shows: the real past cases (finding one by its number, picking one at random,
// and what happened next) and made-up ones, and the forecast for a case on a day of its life. No DOM
// access.

import { MONTH, stillOpen } from './forecast.js';
import { normalise } from './courts.js';

const FINAL = 'ST_VEC_PUK';
const CLOSED = 'ST_VEC_ODS';

/** Cases in order: by court (as `courts` lists them), then year, senate and number. */
export function ordered(cases, courts) {
  const place = new Map(courts.map((court, i) => [court, i]));
  return [...cases].sort((a, b) => (place.get(a.court) - place.get(b.court))
    || a.year - b.year || a.senate - b.senate || a.number - b.number);
}

/**
 * The cases whose number matches a query, in the order given: "42/2024", "9 C 42" and "9 c 42 2024" all
 * find 9 C 42/2024. A match on whole parts of the number comes first. An empty query gives them all.
 */
export function findCases(cases, query) {
  const key = normalise(query ?? '');
  if (!key) return cases;
  const whole = [];
  const part = [];
  for (const item of cases) {
    const label = ` ${normalise(item.label)} `;
    if (label.includes(` ${key} `)) whole.push(item);
    else if (label.includes(` ${key}`)) part.push(item);
  }
  return [...whole, ...part];
}

/** A case picked at random from `cases`, other than `current` if there's a choice. */
export function pick(cases, current = null, random = Math.random) {
  const others = cases.length > 1 ? cases.filter((item) => item !== current) : cases;
  return others[Math.floor(random() * others.length)] ?? null;
}

/** The events the network reads for a forecast at the end of day `day`: those on or before it. */
export const soFar = (item, day) => item.events.filter((event) => event.day <= day && event.day < item.span);

/**
 * The chance a case is still open 1, 2, ... 36 months after the end of day `day`, given its court and its
 * events so far. With no court, it's the courts' forecasts averaged, weighted by their cases registered.
 */
export function forecast(data, court, events, day) {
  const where = court ? court.index : data.courts.map((c) => [c.index, c.journey.registered / data.registered]);
  return stillOpen(data.network, where, events.map((event) => [event.code.index, event.day]), day);
}

/** How the case ended: 'final' (legally final), 'closed' (closed in the register without that) or 'open'. */
export function ending(item) {
  if (!item.ended) return 'open';
  const last = item.events.filter((event) => event.day === item.span).map((event) => event.code.code);
  return last.includes(FINAL) || !last.includes(CLOSED) ? 'final' : 'closed';
}

/**
 * Whether the case ended within `months` months of the end of day `day`: 'yes', 'no', or 'unknown' if
 * its record runs out before then with the case still open. As the scores count it.
 */
export function outcome(item, day, months) {
  const left = item.span - day;
  const horizon = months * MONTH;
  if (item.ended && left <= horizon) return 'yes';
  return left >= horizon ? 'no' : 'unknown';
}

/** The most events a made-up case can have (real ones have up to 49 before their end). */
export const MOST_EVENTS = 30;

// The events a made-up case can have, in about the order a case meets them: every code the network
// learned from but the filing (always first), "legally final" and "closed in the register" (each ends
// a case), and a Supreme Court review (in one training case). A decision and the disposal share a day
// in 96% of cases, so they're offered together too.
const OFFERED = [['NAR_JED'], ['VYD_ROZH', 'ST_VEC_VYR'], ['VYD_ROZH'], ['ST_VEC_VYR'], ['POD_OP_PR'], ['ODES_SPIS'],
  ['ODVOLANI'], ['NAD_RIZENI'], ['VYR_OP_PR'], ['VRAC_SPIS'], ['ST_VEC_OBZ'], ['ST_VEC_PRE'], ['ST_VEC_UPR']];

/** The events a made-up case can have, as { label, codes }, each code one of `data.codes`. */
export function offered(data) {
  const byCode = new Map(data.codes.map((code) => [code.code, code]));
  return OFFERED.map((names) => {
    const codes = names.map((name) => byCode.get(name));
    const [first, ...rest] = codes.map((code) => code.gloss);
    return { label: [first, ...rest.map((gloss) => gloss[0].toLowerCase() + gloss.slice(1))].join(', and '), codes };
  });
}

/**
 * A made-up case: its court (or null, for all courts) and its events, from its filing on day 0, with
 * `added`, how many events each thing added brought, so they can be taken back.
 */
export function madeUp(data, court) {
  const filing = data.codes.find((code) => code.code === 'ZAHAJ_RIZ');
  return { made: true, label: 'Made-up case', court, events: [{ code: filing, day: 0 }], added: [], span: Infinity, ended: false };
}

/** The made-up case with `codes` added on day `day`, if that's on or after its last event's and they fit. */
export function add(item, codes, day) {
  if (day < item.events.at(-1).day || item.events.length + codes.length > MOST_EVENTS) return item;
  return { ...item, events: [...item.events, ...codes.map((code) => ({ code, day }))], added: [...item.added, codes.length] };
}

/** The made-up case without the last thing added. */
export function undo(item) {
  if (!item.added.length) return item;
  return { ...item, events: item.events.slice(0, -item.added.at(-1)), added: item.added.slice(0, -1) };
}
