// The process map's numbers, for the whole country or a court: the moves between stages, the commonest
// route, and the share of cases still waiting each month after filing. No DOM access.

/**
 * Where each stage sits on the map, as fractions of its width and height: the usual route along the
 * middle, revivals above it, and suspensions, appeals and closing in the register below.
 */
export const PLACES = {
  filed: [0.04, 0.5],
  hearing: [0.33, 0.5],
  decided: [0.63, 0.5],
  final: [0.95, 0.5],
  revived: [0.48, 0.1],
  suspended: [0.18, 0.9],
  appeal: [0.79, 0.9],
  closed: [0.95, 0.9],
};

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

/** A scope's commonest route from filing to its end, as { stages, ending, share }. */
export function commonest(journey, stages) {
  const [path, ending, share] = journey.paths.reduce((best, path) => (path[2] > best[2] ? path : best));
  return { stages: path.map((i) => stages[i]), ending, share };
}

/** The share of cases not yet decided, and not yet legally final, `month` months after filing. */
export const waiting = (journey, month) => ({ decided: journey.notDecided[month], final: journey.notFinal[month] });
