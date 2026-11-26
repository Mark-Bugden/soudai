// Reading a chart off its y axis, the same on every chart: at the point hovered, a line up the chart, a
// dot on each series, a faint line from each dot to the y axis, and the value there. The axis's own
// labels make way. There are no tooltips: whatever a chart shows can be read off its axes, or is in its
// description.

import { s } from './dom.js';

const LINE = 15; // px between values on the axis

/**
 * Places labels as near the positions `wanted` as they can be while at least `apart` px apart, in the same
 * order. Labels that would overlap form a block centred where its labels want to be, on average, and
 * blocks that then overlap merge, so any number of crowded labels come apart.
 */
export function stack(wanted, apart) {
  const order = wanted.map((at, i) => i).sort((a, b) => wanted[a] - wanted[b]);
  const blocks = []; // { members, sum }: a block's first label goes at sum / members.length
  for (const i of order) {
    let block = { members: [i], sum: wanted[i] };
    for (let last = blocks.at(-1); last && last.sum / last.members.length + last.members.length * apart > block.sum / block.members.length; last = blocks.at(-1)) {
      blocks.pop();
      // The block's labels each sit `apart` further down than the one before.
      block = { members: [...last.members, ...block.members], sum: last.sum + block.sum - block.members.length * last.members.length * apart };
    }
    blocks.push(block);
  }
  const placed = [...wanted];
  for (const { members, sum } of blocks) members.forEach((i, k) => { placed[i] = sum / members.length + k * apart; });
  return placed;
}

/**
 * Draws a reading in `group`: a line up the chart at `x`, from `top` to `bottom`, and for each of `values`
 * ({ cx, at, text, dot, r }) a dot of class `dot` at (cx, at), a faint line from it to the y axis at
 * `left`, and `text` beside the axis, `inset` px from it, where its ticks are. Hides the `ticks`
 * ({ tick, at }) that the values would cover.
 */
export function showReading(group, { x, top, bottom, left, inset = 8, values, ticks = [] }) {
  const labels = stack(values.map(({ at }) => at), LINE);
  group.replaceChildren(
    s('line', { class: 'sd-cross-line', x1: x, x2: x, y1: top, y2: bottom }),
    ...values.map(({ cx, at }) => s('line', { class: 'sd-reading-line', x1: left, x2: cx, y1: at, y2: at })),
    ...values.map(({ cx, at, dot, r = 4 }) => s('circle', { class: dot, cx, cy: at, r })),
    ...values.map(({ text }, i) => s('text', { class: 'sd-reading-value', x: left - inset, y: labels[i], dy: '0.32em', 'text-anchor': 'end' }, text)),
  );
  for (const { tick, at } of ticks) tick.classList.toggle('is-under', labels.some((label) => Math.abs(label - at) < LINE));
}

/** Takes a reading away, and gives the axis its labels back. */
export function clearReading(group, ticks = []) {
  group.replaceChildren();
  for (const { tick } of ticks) tick.classList.remove('is-under');
}
