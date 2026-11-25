// The real past cases: finding one by its number, picking one at random, the forecast for it on a day of
// its life, and what happened next. No DOM access.

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

/** The chance the case is still open 1, 2, ... 36 months after the end of day `day`. */
export function forecast(data, court, events, day) {
  return stillOpen(data.network, court.index, events.map((event) => [event.code.index, event.day]), day);
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
