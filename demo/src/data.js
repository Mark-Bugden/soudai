// The demo's data, data/soudai.json (written by `uv run soudai export`), with lookups the views share.
// No DOM access.

import { network } from './forecast.js';

const DAY = 864e5;

// The lane on a case's timeline of the event codes that are on no stage of the journey map.
const LANES = { ST_VEC_ODS: 'closed', ST_VEC_UPR: 'suspended' };

/**
 * The data with each court given its row (`index`, its place in the network's rows), its journey and
 * its real past cases, plus:
 * - `journey(court)`: the journey numbers for a court, or for the whole country when it's null;
 * - `codes`, each with its row and its `lane` on a case's timeline (its stage, or the stage it ends);
 * - `cases`: the real past cases, each with its court, its number, its filing date, `span` (days from
 *   filing to its end, or to the day its record runs to), `ended`, and its events as { code, day };
 * - `network`: the ensemble, decoded for `forecast.stillOpen`.
 */
export function prepare(raw) {
  const courts = raw.courts.map((court, index) => ({ ...court, index, journey: raw.journey[court.code], cases: [] }));
  const byCode = new Map(courts.map((court) => [court.code, court]));
  const codes = raw.codes.map((code, index) => ({ ...code, index, lane: code.stage ?? LANES[code.code] ?? null }));
  const split = Date.parse(`${raw.split}T00:00:00Z`);
  const cases = raw.cases.rows.map(([court, senate, number, year, filed, span, ended, pairs], index) => {
    const events = [];
    for (let i = 0; i < pairs.length; i += 2) events.push({ code: codes[pairs[i]], day: pairs[i + 1] });
    return {
      index,
      court: courts[court],
      senate,
      number,
      year,
      label: `${senate} C ${number}/${year}`,
      filed: new Date(split + filed * DAY),
      span,
      ended: Boolean(ended),
      events,
    };
  });
  for (const item of cases) item.court.cases.push(item);
  return {
    ...raw,
    courts,
    codes,
    cases,
    network: network(raw.network),
    court: (code) => byCode.get(code) ?? null,
    journey: (court) => (court ? court.journey : raw.journey.all),
  };
}
