// Text for the status line and the court search. No DOM access.

const NUMBER = new Intl.NumberFormat('en-GB');

/** A whole number with thousands separators: 1,725,672. */
export const count = (n) => NUMBER.format(n);

/** "1 day" or "149 days". */
export const days = (n) => `${count(n)} ${n === 1 ? 'day' : 'days'}`;

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
