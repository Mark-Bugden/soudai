// Court search: finds a court by its name or its area, ignoring diacritics, so "Decin" finds Děčín.
// No DOM access.

/** Lower case, without diacritics or punctuation, so "Děčín" matches "decin". */
export function normalise(text) {
  return text
    .normalize('NFKD').replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

/** The courts in order of their areas, as Czech sorts them (Praha 2 before Praha 10), with their search keys. */
export function searchIndex(courts) {
  return [...courts]
    .sort((a, b) => a.area.localeCompare(b.area, 'cs', { numeric: true }))
    .map((court) => ({ court, area: normalise(court.area), name: normalise(court.name) }));
}

// How well a key matches a query, best first: the whole key, its start, the start of a word in it,
// or anywhere in it.
function closeness(key, query) {
  if (key === query) return 0;
  if (key.startsWith(query)) return 1;
  if (key.includes(` ${query}`)) return 2;
  if (key.includes(query)) return 3;
  return null;
}

/**
 * The courts that match a query, best first: by their area, then by their full name, each in order of
 * area. An empty query gives every court, in order of area.
 */
export function matches(index, query) {
  const key = normalise(query ?? '');
  if (!key) return index.map((entry) => entry.court);
  const ranked = Array.from({ length: 8 }, () => []);
  for (const entry of index) {
    const byArea = closeness(entry.area, key);
    const byName = closeness(entry.name, key);
    const rank = byArea ?? (byName === null ? null : 4 + byName);
    if (rank !== null) ranked[rank].push(entry.court);
  }
  return ranked.flat();
}
