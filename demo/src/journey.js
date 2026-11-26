// The process map's numbers, for the whole country or a court: the moves between stages, which of them
// the map draws, the commonest route, and the share of cases legally final each month after filing.
// No DOM access.

/**
 * Where each stage sits on the map, as fractions of its width and of the height between its two rows:
 * the usual route along the top row, and below it suspensions, revivals and appeals, each between the
 * two stages it most often joins, and closing in the register under legally final.
 */
export const PLACES = {
  filed: [0, 0],
  hearing: [0.33, 0],
  decided: [0.66, 0],
  final: [1, 0],
  suspended: [0.165, 1],
  revived: [0.495, 1],
  appeal: [0.83, 1],
  closed: [1, 1],
};

/** The share of cases a move needs to be drawn on the map. */
export const DRAWN = 0.02;

// The pairs of stages next to each other on the map, which a straight arrow joins.
const NEXT = new Set(['filed hearing', 'hearing decided', 'decided final', 'filed suspended', 'hearing suspended',
  'hearing revived', 'decided revived', 'decided appeal', 'final appeal', 'final closed', 'suspended revived',
  'revived appeal', 'appeal closed']);

/**
 * How the map draws a move: 'line' between stages next to each other, 'arc' from filing to a decision,
 * over the hearing, and null for any other move, which would cross a stage.
 */
export function shape(from, to) {
  if (NEXT.has(`${from} ${to}`) || NEXT.has(`${to} ${from}`)) return 'line';
  return from === 'filed' && to === 'decided' ? 'arc' : null;
}

/**
 * A scope's moves, from the commonest: { from, to, share, sampled, wait }, where `from` and `to` are
 * stages (or "closed"), `share` the share of cases making the move at least once, and `wait` the
 * quartiles of its wait in days, [p25, median, p75], or null where too few sampled cases made it.
 */
export function moves(journey, stages) {
  return journey.moves
    .map(([from, to, share, sampled, p25, median, p75]) => ({
      from: stages[from],
      to: stages[to],
      share,
      sampled,
      wait: median === null ? null : [p25, median, p75],
    }))
    .sort((a, b) => b.share - a.share);
}

/** The moves the map draws, made by at least DRAWN of cases and with a shape, and the rest, each in the order given. */
export function split(list) {
  const drawn = list.filter((move) => move.share >= DRAWN && shape(move.from, move.to));
  return { drawn, rest: list.filter((move) => !drawn.includes(move)) };
}

/** A scope's commonest route from filing to its end, as { stages, ending, share }. */
export function commonest(journey, stages) {
  const [path, ending, share] = journey.paths.reduce((best, path) => (path[2] > best[2] ? path : best));
  return { stages: path.map((i) => stages[i]), ending, share };
}

/** The share of cases legally final each month after filing, from 0. */
export const legallyFinal = (journey) => journey.notFinal.map((open) => 1 - open);
