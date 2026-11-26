// Text for the status line, the controls and the views. No DOM access.

const NUMBER = new Intl.NumberFormat('en-GB');
const DATE = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
const SHORT_DATE = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
const DAY = 864e5;

/** The stages on the journey map, and "closed in the register", by the names the export gives them. */
export const STAGES = {
  filed: 'Filed',
  hearing: 'Hearing',
  decided: 'Decided',
  appeal: 'Appeal',
  revived: 'Revived',
  suspended: 'Suspended',
  final: 'Legally final',
  closed: 'Closed',
};

/** A whole number with thousands separators: 1,725,672. */
export const count = (n) => NUMBER.format(n);

/** "1 day" or "149 days". */
export const days = (n) => `${count(n)} ${n === 1 ? 'day' : 'days'}`;

/** "1 month" or "12 months". */
export const months = (n) => `${n} ${n === 1 ? 'month' : 'months'}`;

/** A chance as a whole percent, "45%", with "<1%" and ">99%" for chances that would round to 0 or 100. */
export function percent(p) {
  if (p < 0.005) return '<1%';
  if (p >= 0.995) return '>99%';
  return `${Math.round(p * 100)}%`;
}

/** "3 June 2024", or "3 Jun 2024" when `short`. */
export const date = (when, short = false) => (short ? SHORT_DATE : DATE).format(when);

/** The date `n` days after `start`. */
export const addDays = (start, n) => new Date(start.getTime() + n * DAY);

/** "13,940 cases registered", for a journey's count of cases. */
export const registered = (journey) => `${count(journey.registered)} cases registered`;

/**
 * The status line for a court, or for all courts when it's null: what's selected, the cases it
 * registered in the years covered, and the median times to a decision and to legally final.
 */
export function headline(court, journey, courts) {
  const who = court ? court.name : `All ${courts} courts`;
  const [, decided] = journey.decided;
  const [, final] = journey.final;
  return `${who}: ${registered(journey)} in 2020–2025. Median time from filing to a decision ${days(decided)}, `
    + `and to legally final ${days(final)}.`;
}

/** What happened to a real case after day `day`: "It became legally final 23 days later." */
export function next(item, ending, day) {
  const later = days(item.span - day);
  if (ending === 'final') return `It became legally final ${later} later.`;
  if (ending === 'closed') return `It was closed in the register ${later} later.`;
  return `It was still open ${later} later, on ${date(addDays(item.filed, item.span))}, when its record ends.`;
}

/** "a, b, c and d". */
const list = (items) => (items.length > 1 ? `${items.slice(0, -1).join(', ')} and ${items.at(-1)}` : items[0]);

/** "at filing", or "on 3 June 2024, day 80". */
export const moment = (filed, day) => (day === 0 ? 'at filing' : `on ${date(addDays(filed, day))}, day ${count(day)}`);

/** "Chance it ends: 1% within 1 month, ... and 92% within 12 months." */
const chancesText = (chances, horizons) => `Chance it ends: ${list(horizons.map((h, i) => `${percent(chances[i])} within ${months(h)}`))}.`;

/**
 * The status line for a forecast on a real case: the case, the day, the chance it ends within a few
 * months, and what happened next.
 */
export function forecastLine(item, day, chances, horizons, ending) {
  return `${item.label}, ${item.court.name}, ${moment(item.filed, day)}. ${chancesText(chances, horizons)} `
    + next(item, ending, day);
}

/** The status line for a forecast on a custom case: its court, the day, the chances, and its last event. */
export function customLine(item, day, chances, horizons) {
  const last = item.events.at(-1);
  const after = item.events.length > 1 ? ` Its last event: ${last.code.gloss}, ${moment(item.filed, last.day)}.` : '';
  return `Custom case, ${item.court.name}, ${moment(item.filed, day)}. ${chancesText(chances, horizons)}${after}`;
}

/** A wait in days: "same day", "1 day" or "30 days". */
export const wait = (n) => (n === 0 ? 'same day' : days(n));

/** A route through the stages: "filed → hearing → decided → legally final". */
export const route = (stages) => stages.map((stage) => STAGES[stage].toLowerCase()).join(' → ');

/** A share of cases to one decimal place, for the map: "93.3%", or "<0.1%". */
export const share = (p) => (p < 0.0005 ? '<0.1%' : `${(p * 100).toFixed(1)}%`);

/** A complete route, with how it ended if not legally final: "filed → decided → closed", "filed → hearing, still open". */
export function routeText({ stages, ending }) {
  if (ending === 'closed') return route([...stages, 'closed']);
  return ending === 'open' ? `${route(stages)}, still open` : route(stages);
}

/** An arrow's label on the map, as its lines: the share of cases making the move, and its median wait if known. */
export const moveLabel = (m) => [share(m.share), ...(m.wait ? [wait(m.wait[1])] : [])];

/** The note under the map, if it leaves any moves out (Mark's wording). */
export const notShown = (rest) => (rest.length ? 'Not shown: paths followed by less than 2% of cases.' : '');
