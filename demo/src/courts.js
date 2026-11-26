// The courts by type and place, for the court menus: "Okresní soud", then "Děčín". No DOM access.

/** The types of court, in the order the menu lists them. A court's name starts with its type. */
export const TYPES = ['Okresní soud', 'Obvodní soud', 'Městský soud'];

/**
 * The courts grouped by type, in the order of TYPES, as { type, courts: [{ court, place }] }. A court's
 * place is its name without its type ("Děčín", "Praha 1", "Brno"), and each type's courts are in order
 * of place, as Czech sorts them: "ch" after "h", and Praha 2 before Praha 10.
 */
export function byType(courts) {
  const groups = TYPES.map((type) => ({ type, courts: [] }));
  for (const court of courts) {
    const group = groups.find(({ type }) => court.name.startsWith(`${type} `));
    if (!group) throw new Error(`${court.name}: not a court of a known type`);
    group.courts.push({ court, place: court.name.slice(group.type.length + 1) });
  }
  for (const group of groups) group.courts.sort((a, b) => a.place.localeCompare(b.place, 'cs', { numeric: true }));
  return groups.filter((group) => group.courts.length);
}
