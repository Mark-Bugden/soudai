// The cases the Forecast tab shows: the real past cases (in order, picking one at random, and what
// happened next) and custom ones, and the forecast for a case on a day of its life. No DOM access.

import { MONTH, stillOpen } from './forecast.js';

const FINAL = 'ST_VEC_PUK';
const CLOSED = 'ST_VEC_ODS';
const DAY = 864e5;

/** Cases in order of year, senate and number. */
export function ordered(cases) {
  return [...cases].sort((a, b) => a.year - b.year || a.senate - b.senate || a.number - b.number);
}

/** A case picked at random from `cases`, other than `current` if there's a choice. */
export function pick(cases, current = null, random = Math.random) {
  const others = cases.length > 1 ? cases.filter((item) => item !== current) : cases;
  return others[Math.floor(random() * others.length)] ?? null;
}

/** The events the network reads for a forecast at the end of day `day`: those on or before it. */
export const soFar = (item, day) => item.events.filter((event) => event.day <= day && event.day < item.span);

/** The chance a case is still open 1, 2, ... 36 months after the end of day `day`, given its court and its events so far. */
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

/** The most events a custom case can have (real ones have up to 49 before their end). */
export const MOST_EVENTS = 30;

/** The latest a custom case's events and forecast can come, in days after its filing: 36 months. */
export const LONGEST = 1096;

// The events a custom case can have, in about the order a case meets them: every code the network
// learned from but the filing (always first), "legally final" and "closed in the register" (each ends
// a case), and a Supreme Court review (in one training case). A decision and the disposal share a day
// in 96% of cases, so they're offered together too.
const OFFERED = [['NAR_JED'], ['VYD_ROZH', 'ST_VEC_VYR'], ['VYD_ROZH'], ['ST_VEC_VYR'], ['POD_OP_PR'], ['ODES_SPIS'],
  ['ODVOLANI'], ['NAD_RIZENI'], ['VYR_OP_PR'], ['VRAC_SPIS'], ['ST_VEC_OBZ'], ['ST_VEC_PRE'], ['ST_VEC_UPR']];

/** The events a custom case can have, as { label, codes }, each code one of `data.codes`. */
export function offered(data) {
  const byCode = new Map(data.codes.map((code) => [code.code, code]));
  return OFFERED.map((names) => {
    const codes = names.map((name) => byCode.get(name));
    const [first, ...rest] = codes.map((code) => code.gloss);
    return { label: [first, ...rest.map((gloss) => gloss[0].toLowerCase() + gloss.slice(1))].join(', and '), codes };
  });
}

/**
 * A custom case at `court`, filed on `filed` (a date at midnight UTC), with only its filing. Its events
 * are { code, day }, in days after filing, as a real case's are, in order of day and then of adding.
 */
export function custom(data, court, filed) {
  const filing = data.codes.find((code) => code.code === 'ZAHAJ_RIZ');
  return { made: true, label: 'Custom case', court, filed, events: [{ code: filing, day: 0 }], span: Infinity, ended: false };
}

/** The custom case with `codes` added on day `day`, after any events on that day, if the day is in range and they fit. */
export function add(item, codes, day) {
  if (day < 0 || day > LONGEST || item.events.length + codes.length > MOST_EVENTS) return item;
  const at = item.events.findIndex((event) => event.day > day);
  const events = [...item.events];
  events.splice(at < 0 ? events.length : at, 0, ...codes.map((code) => ({ code, day })));
  return { ...item, events };
}

/** The custom case without its event `i`. The filing, event 0, stays. */
export function remove(item, i) {
  if (i < 1 || i >= item.events.length) return item;
  return { ...item, events: item.events.filter((_, j) => j !== i) };
}

/**
 * The days on which a custom case's filing can fall, counted from its present filing: no later than its
 * first event, and no more than LONGEST days before its last. With no events, any day.
 */
export function filingRange(item) {
  if (item.events.length === 1) return [-Infinity, Infinity];
  return [item.events.at(-1).day - LONGEST, item.events[1].day];
}

/** The custom case filed `shift` days later (earlier if negative), its events keeping their dates. */
export function refile(item, shift) {
  const [earliest, latest] = filingRange(item);
  const by = Math.min(Math.max(shift, earliest), latest);
  if (by === 0) return item;
  return {
    ...item,
    filed: new Date(item.filed.getTime() + by * DAY),
    events: item.events.map((event, i) => (i ? { ...event, day: event.day - by } : event)),
  };
}
