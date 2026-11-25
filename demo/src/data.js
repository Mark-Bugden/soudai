// The demo's data, data/soudai.json (written by `uv run soudai export`), with lookups the views share.
// No DOM access.

/**
 * The data with each court given its row (`index`, its place in the network's rows) and its journey,
 * plus `journey(court)`: the journey numbers for a court, or for the whole country when it's null.
 */
export function prepare(raw) {
  const courts = raw.courts.map((court, index) => ({ ...court, index, journey: raw.journey[court.code] }));
  const byCode = new Map(courts.map((court) => [court.code, court]));
  return {
    ...raw,
    courts,
    court: (code) => byCode.get(code) ?? null,
    journey: (court) => (court ? court.journey : raw.journey.all),
  };
}
