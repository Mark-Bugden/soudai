// The Process map tab: how civil cases move between the stages, for the whole country or the court
// selected, beside the share of cases legally final each month after filing.
//
// - The map: a node per stage (see journey.PLACES) and an arrow per move made by at least 2% of cases,
//   its width that share. Arrows join only stages next to each other, straight, but for the arc from
//   filing to a decision, over the hearing; a move and its reverse sit side by side. Each arrow is
//   labelled with its share and median wait: set into the line where it's thin, and beside it where
//   it's thick, wherever nothing else is (into the line too, if nowhere beside it is clear). The moves not drawn are listed under the map, and a hidden
//   table gives every move to screen readers. Hovering an arrow dims the others and their labels.
// - The curve: the court's, in the accent, against all courts', in the curve colour.
//
// Colours come from CSS classes (see demo.css), so a theme change needs no redraw.

import { h, s } from '../dom.js';
import * as describe from '../format.js';
import { PLACES, commonest, legallyFinal, moves, shape, split } from '../journey.js';
import { createTooltip } from '../tooltip.js';

const MONTHS = 24; // months after filing on the curve
const LINE = 15; // px, a label's line height
const NODE = 7; // px, a stage's radius
const GAP = NODE + 3; // px between a stage and the arrows that leave or reach it
const ARROW = 8; // px, the length of an arrowhead
const THICK = 10; // px: an arrow at least this wide has its label beside it rather than on it
const NARROW = 480; // px: on a map narrower than this, a stage's name can take two lines

export function createMap(host, data) {
  const meta = h('p', { class: 'sd-case-meta' });
  const key = h('p', { class: 'sd-note' }, 'Shares are of all cases, and waits are medians. An arrow\'s width is its share.');
  const mapSvg = s('svg', { class: 'sd-chart sd-flow', 'aria-hidden': 'true' });
  const mapBox = h('div', { class: 'sd-chart-box sd-map-box' }, mapSvg);
  const rest = h('p', { class: 'sd-note' });
  const legend = h('p', { class: 'sd-legend' });
  const curveSvg = s('svg', { class: 'sd-chart', 'aria-hidden': 'true' });
  const curveBox = h('div', { class: 'sd-chart-box' }, curveSvg);
  const table = h('table', { class: 'sd-sr-only' });
  const el = h('div', { class: 'sd-map' },
    h('div', { class: 'sd-case' }, h('p', { class: 'sd-case-title' }, 'Process map'), meta),
    h('div', { class: 'sd-map-body' },
      h('div', { class: 'sd-map-flow' }, key, mapBox, rest),
      h('div', { class: 'sd-curves' }, h('p', { class: 'sd-cal-title' }, 'Share legally final'), legend, curveBox)),
    table);
  host.append(el);
  const tip = createTooltip(curveBox);
  let curve = null; // what the curve's crosshair needs
  const ruler = document.createElement('canvas').getContext('2d');

  /** The width of a label's text in px, in the map's font: its 12px, bold for a stage's name. */
  function measure(text, bold = false) {
    ruler.font = `${bold ? 600 : 400} 12px ${getComputedStyle(mapSvg).fontFamily}`;
    return ruler.measureText(text).width;
  }

  function render({ court }) {
    const journey = data.journey(court);
    const route = commonest(journey, data.stages);
    // The status line gives the court and its cases registered.
    meta.textContent = `Commonest route: ${describe.route(route.stages)}, ${describe.share(route.share)} of cases.`;
    const list = moves(journey, data.stages);
    const { drawn, rest: left } = split(list);
    describeMoves(list);
    rest.textContent = describe.notDrawn(left);
    drawMap(journey, drawn);
    legend.replaceChildren(...(court
      ? [h('span', { class: 'sd-key sd-key-model' }), h('span', { class: 'sd-legend-name' }, court.area),
        h('span', { class: 'sd-key sd-key-diagonal' }), 'All courts']
      : []));
    curve = drawCurve(court, court ? legallyFinal(journey) : null, legallyFinal(data.journey(null)));
    tip.hide();
  }

  /** The hidden table of every move, for screen readers. */
  function describeMoves(list) {
    table.replaceChildren(
      h('caption', {}, 'Moves between stages'),
      h('thead', {}, h('tr', {}, ...['From', 'To', 'Share of cases', 'Median wait', 'Middle half of waits'].map((name) => h('th', { scope: 'col' }, name)))),
      h('tbody', {}, ...list.map((move) => h('tr', {},
        h('td', {}, describe.STAGES[move.from]),
        h('td', {}, describe.STAGES[move.to]),
        h('td', {}, describe.share(move.share)),
        h('td', {}, move.wait ? describe.wait(move.wait[1]) : 'too few cases'),
        h('td', {}, move.wait ? `${describe.count(move.wait[0])}–${describe.days(move.wait[2])}` : '')))));
  }

  function drawMap(journey, drawn) {
    const width = mapBox.clientWidth;
    const height = mapBox.clientHeight;
    size(mapSvg, width, height);
    if (width < 160 || height < 120) {
      mapSvg.replaceChildren();
      return;
    }
    const shares = new Map(data.stages.map((stage, i) => [stage, i < journey.stages.length ? journey.stages[i] : null]));
    const shareText = (stage) => (shares.get(stage) === null ? null : (shares.get(stage) > 0.9995 ? '100%' : describe.share(shares.get(stage))));
    const widest = Math.max(8, Math.min(24, Math.min(width, height) * 0.05));
    const stroke = (share) => 1 + (widest - 1) * share;
    const arcWidth = stroke(drawn.find((move) => shape(move.from, move.to) === 'arc')?.share ?? 0);

    // The rows: the arc over the hearing clears the hearing's label, with room for its own above it.
    const lift = Math.max(NODE + 2 * LINE + 10 + arcWidth / 2, 0.2 * height);
    const pad = {
      left: Math.max(measure('Filed', true), measure(shareText('filed') ?? '')) + NODE + 12,
      right: NODE + 4,
      top: LINE + 10 + arcWidth / 2 + lift,
      bottom: NODE + 2 * LINE + 6,
    };
    const at = (stage) => [pad.left + PLACES[stage][0] * (width - pad.left - pad.right), pad.top + PLACES[stage][1] * (height - pad.top - pad.bottom)];

    // What labels must keep clear of: the stages and their labels, the arrows, and the other labels.
    const taken = [];
    const nodes = s('g', { class: 'sd-nodes' });
    const shown = new Set(drawn.flatMap((move) => [move.from, move.to]));
    for (const stage of data.stages) {
      if (stage === 'closed' && !shown.has('closed')) continue;
      const [x, y] = at(stage);
      // On a narrow map "Legally final" takes two lines, to keep clear of "Decided".
      const name = width < NARROW ? describe.STAGES[stage].split(' ') : [describe.STAGES[stage]];
      const lines = [...name, ...(shareText(stage) ? [shareText(stage)] : [])];
      const wide = Math.max(...lines.map((text, j) => measure(text, j < name.length))) + 2;
      // Filing's label is on its left. The top row's are above, the bottom row's below; decided's starts
      // at the stage, clear of the arc that ends there.
      let box;
      let anchor;
      if (stage === 'filed') {
        anchor = 'end';
        box = [x - NODE - 6 - wide, y - LINE, x - NODE - 6, y + LINE];
      } else {
        const top = PLACES[stage][1] === 0 ? y - NODE - 4 - LINE * lines.length : y + NODE + 4;
        anchor = { decided: 'start', final: 'end', closed: 'end' }[stage] ?? 'middle';
        const x0 = { start: x - 3, end: x + NODE - wide, middle: x - wide / 2 }[anchor];
        box = [x0, top, x0 + wide, top + LINE * lines.length];
      }
      const tx = { start: box[0], end: box[2], middle: (box[0] + box[2]) / 2 }[anchor];
      nodes.append(s('circle', { class: 'sd-node', cx: x, cy: y, r: NODE }));
      lines.forEach((text, j) => {
        nodes.append(s('text', { class: j < name.length ? 'sd-node-label' : 'sd-node-share', x: tx, y: box[1] + LINE * j + 11, 'text-anchor': anchor }, text));
      });
      taken.push([x - NODE, y - NODE, x + NODE, y + NODE], box);
    }

    // The arrows, a move and its reverse side by side.
    const arrows = drawn.map((move) => {
      const w = stroke(move.share);
      const reverse = drawn.some((other) => other.from === move.to && other.to === move.from);
      const geometry = shape(move.from, move.to) === 'arc'
        ? arc(at(move.from), at(move.to), w, lift)
        : line(at(move.from), at(move.to), w, reverse ? head(w) + 1.5 : 0);
      return { move, w, geometry };
    });
    const marks = arrows.flatMap(({ move, w, geometry }) => geometry.samples.map(([x, y]) => [x, y, w / 2 + 2, move]));

    // The labels, the commonest first, each where it clears everything placed so far.
    const labels = new Map();
    for (const { move, w, geometry } of arrows) {
      // Beside an arc, its label goes above it, and beside a line, under or right of it first.
      const sides = shape(move.from, move.to) === 'arc' ? [1, -1] : [-1, 1];
      const box = place(describe.moveLabel(move), w, geometry, { width, height, taken, marks, measure }, { sides, on: w < THICK, owner: move });
      taken.push(box.bounds);
      const [x0, y0, x1, y1] = box.bounds;
      labels.set(move, s('g', { class: 'sd-edge-label' },
        box.on ? s('rect', { class: 'sd-edge-label-back', x: x0, y: y0, width: x1 - x0, height: y1 - y0, rx: 3 }) : null,
        s('text', { 'text-anchor': 'middle' }, ...box.lines.map((text, j) => s('tspan', { x: box.x, y: y0 + LINE * j + 11 }, text)))));
    }

    const edges = s('g', { class: 'sd-edges' });
    const hits = [];
    // The rarest first, so the commonest are drawn on top; the hit areas the other way round, so a thin
    // arrow under a thick one can still be found.
    for (const { move, w, geometry } of [...arrows].reverse()) {
      const group = s('g', { class: 'sd-edge' },
        s('path', { class: 'sd-edge-line', d: geometry.path, 'stroke-width': w.toFixed(2) }),
        s('path', { class: 'sd-edge-head', d: geometry.head }));
      edges.append(group);
      const hit = s('path', { class: 'sd-edge-hit', d: geometry.path, 'stroke-width': Math.max(12, w + 6).toFixed(1) });
      const label = labels.get(move);
      hit.addEventListener('pointerenter', () => highlight(group, label, true));
      hit.addEventListener('pointerleave', () => highlight(group, label, false));
      hits.unshift(hit);
    }
    mapSvg.replaceChildren(edges, ...labels.values(), nodes, ...hits);
  }

  /** Hovering an arrow dims the other arrows and their labels. */
  function highlight(group, label, on) {
    mapSvg.classList.toggle('has-hover', on);
    group.classList.toggle('is-hover', on);
    label.classList.toggle('is-hover', on);
  }

  /** The curve: the court's share legally final, if a court is selected, against all courts'. */
  function drawCurve(court, values, all) {
    const width = curveBox.clientWidth;
    const height = curveBox.clientHeight;
    size(curveSvg, width, height);
    if (width < 80 || height < 60) {
      curveSvg.replaceChildren();
      return null;
    }
    const margin = { top: 8, right: 10, bottom: 36, left: 40 };
    const x = (month) => margin.left + (month / MONTHS) * (width - margin.left - margin.right);
    const y = (p) => height - margin.bottom - p * (height - margin.top - margin.bottom);
    const path = (series) => series.slice(0, MONTHS + 1).map((v, m) => `${m ? 'L' : 'M'}${x(m).toFixed(1)},${y(v).toFixed(1)}`).join('');
    const nodes = [];
    for (const p of [0, 0.25, 0.5, 0.75, 1]) {
      nodes.push(
        s('line', { class: p === 0 ? 'sd-axis-line' : 'sd-grid', x1: x(0), x2: x(MONTHS), y1: y(p), y2: y(p) }),
        s('text', { class: 'sd-tick', x: margin.left - 8, y: y(p), dy: '0.32em', 'text-anchor': 'end' }, `${p * 100}%`),
      );
    }
    const step = x(6) - x(0) >= 28 ? 6 : 12;
    for (let m = 0; m <= MONTHS; m += step) {
      nodes.push(s('text', { class: 'sd-tick', x: x(m), y: height - 20, 'text-anchor': 'middle' }, String(m)));
    }
    nodes.push(s('text', { class: 'sd-tick', x: x(MONTHS), y: height - 4, 'text-anchor': 'end' }, 'Months after filing'));
    nodes.push(s('path', { class: values ? 'sd-curve-all' : 'sd-forecast-line', d: path(all) }));
    if (values) nodes.push(s('path', { class: 'sd-forecast-line', d: path(values) }));
    const cross = s('g', { class: 'sd-cross' });
    nodes.push(cross);
    curveSvg.replaceChildren(...nodes);
    return { court, values: values ?? all, all, x, y, cross, left: margin.left, right: width - margin.right };
  }

  // The curve's crosshair: the nearest month, with the values in a tooltip.
  curveSvg.addEventListener('pointermove', (event) => {
    if (!curve) return;
    const box = curveSvg.getBoundingClientRect();
    const month = Math.round(((event.clientX - box.left - curve.left) / (curve.right - curve.left)) * MONTHS);
    if (month < 0 || month > MONTHS) {
      clearCross();
      return;
    }
    const { x, y, court, values, all } = curve;
    curve.cross.replaceChildren(
      s('line', { class: 'sd-cross-line', x1: x(month), x2: x(month), y1: y(1), y2: y(0) }),
      ...(court ? [s('circle', { class: 'sd-curve-dot', cx: x(month), cy: y(all[month]), r: 4 })] : []),
      s('circle', { class: 'sd-forecast-dot', cx: x(month), cy: y(values[month]), r: 4 }),
    );
    const lines = [month ? `${describe.months(month)} after filing` : 'At filing',
      `${court ? court.area : 'All courts'}: ${describe.percent(values[month])} legally final`];
    if (court) lines.push(`All courts: ${describe.percent(all[month])}`);
    tip.show(lines, { x: x(month), y: y(values[month]) - 4 });
  });
  curveSvg.addEventListener('pointerleave', clearCross);

  function clearCross() {
    curve?.cross.replaceChildren();
    tip.hide();
  }

  return {
    render,
    destroy() {
      tip.destroy();
      el.remove();
    },
  };
}

function size(svg, width, height) {
  svg.setAttribute('width', width);
  svg.setAttribute('height', height);
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
}

/** Half the width of an arrowhead on an arrow `width` px wide. */
const head = (width) => Math.max(4.5, width / 2 + 2.5);

const unit = (x, y) => {
  const length = Math.hypot(x, y) || 1;
  return [x / length, y / length];
};

/** An arrowhead at `tip`, pointing along the unit vector [ux, uy]: its path data. */
function arrowhead(tip, [ux, uy], width) {
  const end = [tip[0] - ux * ARROW, tip[1] - uy * ARROW];
  const half = head(width);
  const point = ([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`;
  return `M${point(tip)}L${point([end[0] + uy * half, end[1] - ux * half])}L${point([end[0] - uy * half, end[1] + ux * half])}Z`;
}

/**
 * A straight arrow from one stage to another, moved `shift` px to the left of travel (y runs down), so
 * that a move and its reverse sit side by side: { path, head, at(t), left(t), samples }, where at(t) is
 * the point a share t of the way along, left(t) the unit vector to its left, and samples points along it.
 */
export function line([x0, y0], [x1, y1], width, shift = 0) {
  const [ux, uy] = unit(x1 - x0, y1 - y0);
  const [nx, ny] = [uy, -ux];
  const start = [x0 + ux * GAP + nx * shift, y0 + uy * GAP + ny * shift];
  const tip = [x1 - ux * GAP + nx * shift, y1 - uy * GAP + ny * shift];
  const end = [tip[0] - ux * ARROW, tip[1] - uy * ARROW];
  const at = (t) => [start[0] + (tip[0] - start[0]) * t, start[1] + (tip[1] - start[1]) * t];
  return {
    path: `M${start[0].toFixed(1)},${start[1].toFixed(1)}L${end[0].toFixed(1)},${end[1].toFixed(1)}`,
    head: arrowhead(tip, [ux, uy], width),
    at,
    left: () => [nx, ny],
    samples: Array.from({ length: 25 }, (_, i) => at(i / 24)),
  };
}

/** An arc from one stage to another on the same row, rising `lift` px above it at its middle: as line(). */
export function arc([x0, y0], [x1, y1], width, lift) {
  const rise = lift / 0.75; // a cubic's control points rise 4/3 as far as its middle
  const c0 = [x0 + (x1 - x0) * 0.25, y0 - rise];
  const c1 = [x1 - (x1 - x0) * 0.25, y1 - rise];
  const [sx, sy] = unit(c0[0] - x0, c0[1] - y0);
  const [ex, ey] = unit(x1 - c1[0], y1 - c1[1]);
  const start = [x0 + sx * GAP, y0 + sy * GAP];
  const tip = [x1 - ex * GAP, y1 - ey * GAP];
  const end = [tip[0] - ex * ARROW, tip[1] - ey * ARROW];
  const points = [start, c0, c1, end];
  const at = (t) => {
    const k = [(1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3];
    return [0, 1].map((d) => points.reduce((sum, p, i) => sum + k[i] * p[d], 0));
  };
  const left = (t) => {
    const k = [-3 * (1 - t) ** 2, 3 * (1 - t) ** 2 - 6 * (1 - t) * t, 6 * (1 - t) * t - 3 * t ** 2, 3 * t ** 2];
    const [dx, dy] = [0, 1].map((d) => points.reduce((sum, p, i) => sum + k[i] * p[d], 0));
    const [ux, uy] = unit(dx, dy);
    return [uy, -ux];
  };
  const point = ([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`;
  return {
    path: `M${point(start)}C${point(c0)} ${point(c1)} ${point(end)}`,
    head: arrowhead(tip, [ex, ey], width),
    at,
    left,
    samples: Array.from({ length: 41 }, (_, i) => at(i / 40)),
  };
}

/**
 * Where an arrow's label goes, on one line or two, at the first of a few places along it that clears the
 * map's edges, the boxes in `taken` and the other arrows (`marks`, as [x, y, radius, owner]), with text
 * as wide as `measure(text)` gives. It can be set into the arrow (the `owner` of its marks): with `on`,
 * first, and beside it only where that isn't clear; without, only where nothing beside it is clear.
 * `sides` is the order to try its sides in: 1 for the left of travel (y runs down), -1 for the right.
 * If no place is clear, the one with the fewest clashes. Gives { lines, x, bounds, on }.
 */
export function place(lines, width, geometry, { width: w, height: h, taken, marks, measure }, { sides = [-1, 1], on = false, owner = null } = {}) {
  const formats = [[lines.join(' · ')], lines];
  const placements = on ? [0, ...sides] : [...sides, 0];
  let best = null;
  for (const side of placements) {
    for (const format of formats) {
      const boxWidth = Math.max(...format.map((text) => measure(text))) + 8;
      const boxHeight = LINE * format.length + 2;
      for (const t of [0.5, 0.4, 0.6, 0.3, 0.7]) {
        const [nx, ny] = geometry.left(t);
        const reach = side ? width / 2 + 5 + Math.abs(nx) * (boxWidth / 2) + Math.abs(ny) * (boxHeight / 2) : 0;
        const [px, py] = geometry.at(t);
        const cx = px + side * nx * reach;
        const cy = py + side * ny * reach;
        const bounds = [cx - boxWidth / 2, cy - boxHeight / 2, cx + boxWidth / 2, cy + boxHeight / 2];
        const clashes = (bounds[0] < 0 || bounds[1] < 0 || bounds[2] > w || bounds[3] > h ? 1 : 0)
          + taken.filter(([a, b, c, d]) => bounds[0] < c && a < bounds[2] && bounds[1] < d && b < bounds[3]).length
          + marks.filter(([x, y, r, by]) => (side || by !== owner)
            && x > bounds[0] - r && x < bounds[2] + r && y > bounds[1] - r && y < bounds[3] + r).length;
        const candidate = { lines: format, x: cx, bounds, on: !side, clashes };
        if (!clashes) return candidate;
        if (!best || clashes < best.clashes) best = candidate;
      }
    }
  }
  return best;
}
