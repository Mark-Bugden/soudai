// The process map's numbers, for the whole country or a court: the moves between stages, which of them
// the map draws and how, the commonest routes, and the share of cases legally final each month after
// filing. No DOM access.

/**
 * Where each stage sits on the map, as a fraction of its width and a row: the usual route along the top
 * row (0), and below it (1) suspensions under filing, revivals and appeals each at the bottom of an arc
 * between the two stages they join (see ARCS), and closing in the register under legally final.
 */
export const PLACES = {
  filed: [0, 0],
  hearing: [0.33, 0],
  decided: [0.66, 0],
  final: [1, 0],
  suspended: [0, 1],
  revived: [0.495, 1],
  appeal: [0.83, 1],
  closed: [1, 1],
};

/** The stages at the bottom of an arc below the top row, with the two stages the arc joins. */
export const ARCS = { revived: ['hearing', 'decided'], appeal: ['decided', 'final'] };

/** The share of cases a move needs to be drawn on the map. */
export const DRAWN = 0.02;

// How the map joins the pairs of stages it can: straight along a row or down from filing; over the
// hearing, from filing to a decision; along an arc below the row, to and from revivals and appeals;
// or in a bend, from a suspension to a hearing.
const JOINS = {
  'filed hearing': 'line',
  'hearing decided': 'line',
  'decided final': 'line',
  'filed suspended': 'line',
  'suspended revived': 'line',
  'revived appeal': 'line',
  'filed decided': 'over',
  'hearing revived': 'under',
  'decided revived': 'under',
  'decided appeal': 'under',
  'final appeal': 'under',
  'suspended hearing': 'bend',
};

/**
 * How the map draws a move: 'line', 'over', 'under' or 'bend' (see JOINS), or null for a move between
 * stages it can't join without crossing a stage.
 */
export function shape(from, to) {
  return JOINS[`${from} ${to}`] ?? JOINS[`${to} ${from}`] ?? null;
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

/** A scope's commonest routes from filing to their end, the commonest first, as { stages, ending, share }. */
export function routes(journey, stages) {
  return journey.paths
    .map(([path, ending, share]) => ({ stages: path.map((i) => stages[i]), ending, share }))
    .sort((a, b) => b.share - a.share);
}

/** A scope's commonest route. */
export const commonest = (journey, stages) => routes(journey, stages)[0];

/** The share of cases legally final each month after filing, from 0. */
export const legallyFinal = (journey) => journey.notFinal.map((open) => 1 - open);
