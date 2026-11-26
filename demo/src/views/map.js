// The Process map tab: how civil cases move between the stages, for the whole country or the court
// selected, beside the share of cases legally final each month after filing and the commonest routes.
//
// - The map: a node per stage (see journey.PLACES) and an arrow per move made by at least 2% of cases,
//   its width that share. Arrows join only stages next to each other: straight along the top row and
//   down from filing, in an arc over the hearing from filing to a decision, and along arcs below the
//   row through revivals and appeals. A move and its reverse sit side by side. Each arrow has its share
//   on one side and its median wait on the other, wherever nothing else is. The moves not drawn are
//   listed under the map, and a hidden table gives every move to screen readers. Hovering an arrow dims
//   everything but it, its labels and its two stages.
// - The curve: the court's, in the accent, against all courts', in the curve colour.
// - The routes: the commonest complete routes, each with a bar for its share of cases.
//
// Colours come from CSS classes (see demo.css), so a theme change needs no redraw.

import { h, s } from '../dom.js';
import * as describe from '../format.js';
import { ARCS, PLACES, legallyFinal, moves, routes, shape, split } from '../journey.js';
import { createTooltip } from '../tooltip.js';

const MONTHS = 24; // months after filing on the curve
const ROUTES = 5; // the most routes listed, if they fit
const LINE = 15; // px, a label's line height
const NODE = 7; // px, a stage's radius
const GAP = NODE + 3; // px between a stage and the arrows that leave or reach it
const ARROW = 8; // px, the length of an arrowhead
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
  const routeList = h('ol', { class: 'sd-routes', 'aria-labelledby': 'sd-routes-title' });
  const table = h('table', { class: 'sd-sr-only' });
  const el = h('div', { class: 'sd-map' },
    h('div', { class: 'sd-case' }, h('p', { class: 'sd-case-title' }, 'Process map'), meta),
    h('div', { class: 'sd-map-body' },
      h('div', { class: 'sd-map-flow' }, key, mapBox, rest),
      h('div', { class: 'sd-curves' },
        h('p', { class: 'sd-cal-title' }, 'Share legally final'), legend, curveBox,
        h('p', { class: 'sd-cal-title', id: 'sd-routes-title' }, 'Commonest routes'), routeList)),
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
    meta.textContent = `${court ? court.name : 'All courts'}: ${describe.registered(journey)} in 2020–2025.`;
    const list = moves(journey, data.stages);
    const { drawn, rest: left } = split(list);
    describeMoves(list);
    rest.textContent = describe.notDrawn(left);
    legend.replaceChildren(...(court
      ? [h('span', { class: 'sd-key sd-key-model' }), h('span', { class: 'sd-legend-name' }, court.area),
        h('span', { class: 'sd-key sd-key-diagonal' }), 'All courts']
      : []));
    listRoutes(journey);
    drawMap(journey, drawn);
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

  /** The commonest routes, as many as fit, each with a bar as long as its share. */
  function listRoutes(journey) {
    routeList.replaceChildren(...routes(journey, data.stages).slice(0, ROUTES).map((route) => {
      const bar = h('span', { class: 'sd-route-bar' });
      bar.style.width = `${(route.share * 100).toFixed(2)}%`;
      return h('li', { class: 'sd-route' },
        h('span', { class: 'sd-route-name' }, describe.routeText(route)),
        h('span', { class: 'sd-route-share' }, describe.share(route.share)),
        h('span', { class: 'sd-route-track' }, bar));
    }));
    while (routeList.children.length > 1 && routeList.scrollHeight > routeList.clientHeight + 1) routeList.lastChild.remove();
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
    const overWidth = stroke(drawn.find((move) => shape(move.from, move.to) === 'over')?.share ?? 0);

    // The rows. The arc over the hearing rises about a third of its span, and the shorter arcs below
    // dip half theirs, as far as the height allows, and the drawing is centred in it. The arc over the
    // hearing always clears the hearing's label, and the arcs below leave room for theirs.
    const pad = {
      left: Math.max(measure('Filed', true), measure(shareText('filed') ?? '')) + NODE + 12,
      right: NODE + 4,
      top: LINE + 8 + overWidth / 2,
      bottom: NODE + 4 + 2 * LINE + 2,
    };
    const inner = width - pad.left - pad.right;
    const room = height - pad.top - pad.bottom;
    const least = { lift: NODE + 2 * LINE + 12 + overWidth / 2, depth: 2 * NODE + 2 * LINE + 4 };
    const want = { lift: 0.35 * (PLACES.decided[0] - PLACES.filed[0]) * inner, depth: 0.5 * (PLACES.decided[0] - PLACES.hearing[0]) * inner };
    const fit = Math.min(inner < 400 ? 2 : 1.3, room / (want.lift + want.depth)); // narrow maps need taller arcs for their labels
    const lift = Math.max(least.lift, want.lift * fit);
    const depth = Math.max(least.depth, Math.min(want.depth * fit, room - lift));
    const top = pad.top + Math.max(0, (room - lift - depth) / 2) + lift;
    const at = (stage) => [pad.left + PLACES[stage][0] * inner, top + PLACES[stage][1] * depth];

    // What labels must keep clear of: the stages and their labels, the arrows, and the other labels.
    const taken = [];
    const stages = new Map();
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
        const labelTop = PLACES[stage][1] === 0 ? y - NODE - 4 - LINE * lines.length : y + NODE + 4;
        anchor = { decided: 'start', final: 'end', closed: 'end' }[stage] ?? 'middle';
        const x0 = { start: x - 3, end: x + NODE - wide, middle: x - wide / 2 }[anchor];
        box = [x0, labelTop, x0 + wide, labelTop + LINE * lines.length];
      }
      const tx = { start: box[0], end: box[2], middle: (box[0] + box[2]) / 2 }[anchor];
      const group = s('g', { class: 'sd-stage' }, s('circle', { class: 'sd-node', cx: x, cy: y, r: NODE }),
        ...lines.map((text, j) => s('text', { class: j < name.length ? 'sd-node-label' : 'sd-node-share', x: tx, y: box[1] + LINE * j + 11, 'text-anchor': anchor }, text)));
      stages.set(stage, group);
      taken.push([x - NODE, y - NODE, x + NODE, y + NODE], box);
    }

    // The arrows, a move and its reverse side by side.
    const arrows = drawn.map((move) => {
      const w = stroke(move.share);
      const pair = drawn.some((other) => other.from === move.to && other.to === move.from);
      const points = route(move.from, move.to, at, { lift, depth });
      return { move, w, pair, geometry: arrow(points, w, pair ? head(w) + 1.5 : 0) };
    });
    const marks = arrows.flatMap(({ w, geometry }) => geometry.samples.map(([x, y]) => [x, y, w / 2 + 2]));

    // The labels, the commonest first, each where it clears everything placed so far: the share on one
    // side, the wait on the other, or both on the outside of a move with its reverse beside it.
    const labels = new Map();
    for (const { move, w, pair, geometry } of arrows) {
      const boxes = place(describe.moveLabel(move), w, geometry, { width, height, taken, marks, measure }, { together: pair });
      taken.push(...boxes.map((box) => box.bounds));
      labels.set(move, s('g', { class: 'sd-edge-label' }, ...boxes.map((box) => s('text', { 'text-anchor': 'middle' },
        ...box.lines.map((text, j) => s('tspan', { x: box.x, y: box.bounds[1] + LINE * j + 12 }, text))))));
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
      const lit = [group, labels.get(move), stages.get(move.from), stages.get(move.to)];
      hit.addEventListener('pointerenter', () => highlight(lit, true));
      hit.addEventListener('pointerleave', () => highlight(lit, false));
      hits.unshift(hit);
    }
    mapSvg.replaceChildren(edges, ...labels.values(), ...stages.values(), ...hits);
  }

  /** Hovering an arrow dims everything on the map but it, its labels and its two stages. */
  function highlight(lit, on) {
    mapSvg.classList.toggle('has-hover', on);
    for (const el of lit) el.classList.toggle('is-hover', on);
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
    for (const p of [0, 0.5, 1]) {
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

const mix = ([ax, ay], [bx, by], t) => [ax + (bx - ax) * t, ay + (by - ay) * t];

/** A cubic Bézier curve, as its four points, split in two halves at its middle. */
export function halves([p0, p1, p2, p3]) {
  const [a, b, c] = [mix(p0, p1, 0.5), mix(p1, p2, 0.5), mix(p2, p3, 0.5)];
  const [d, e] = [mix(a, b, 0.5), mix(b, c, 0.5)];
  const m = mix(d, e, 0.5);
  return [[p0, a, d, m], [m, e, c, p3]];
}

/**
 * The curve a move follows on the map, between its stages' centres (`at(stage)`), as a cubic Bézier's
 * four points: straight for a line; for the arc over the hearing, rising `lift` px at its middle; along
 * the arc below the row whose bottom is a revival or an appeal, `depth` px below it; or a bend from a
 * suspension, leaving it sideways and reaching the hearing from below.
 */
export function route(from, to, at, { lift, depth }) {
  const [p, q] = [at(from), at(to)];
  const kind = shape(from, to);
  if (kind === 'line') return [p, mix(p, q, 1 / 3), mix(p, q, 2 / 3), q];
  if (kind === 'over') {
    const rise = lift / 0.75; // a cubic's middle reaches 3/4 of the way to its control points
    return [p, [p[0] + (q[0] - p[0]) / 4, p[1] - rise], [q[0] - (q[0] - p[0]) / 4, q[1] - rise], q];
  }
  if (kind === 'under') {
    const bottom = ARCS[from] ? from : to;
    const row = bottom === to ? from : to;
    const [left, right] = ARCS[bottom].map(at);
    const rise = depth / 0.75;
    const dx = (right[0] - left[0]) / 4;
    const [first, second] = halves([left, [left[0] + dx, left[1] + rise], [right[0] - dx, right[1] + rise], right]);
    // From the row down to the bottom of the arc, then the other way if the move goes up.
    const down = ARCS[bottom][0] === row ? first : [...second].reverse();
    return bottom === to ? down : [...down].reverse();
  }
  // A bend, from a suspension up to the hearing, or back.
  const [low, high] = from === 'suspended' ? [p, q] : [q, p];
  const bend = [low, [low[0] + 0.6 * (high[0] - low[0]), low[1] - 0.15 * (low[1] - high[1])], [high[0], high[1] + 0.6 * (low[1] - high[1])], high];
  return from === 'suspended' ? bend : [...bend].reverse();
}

/**
 * An arrow along a cubic Bézier's four points, moved `shift` px to the left of the line between its ends
 * (y runs down), so that a move and its reverse sit side by side. It starts and ends clear of its
 * stages. Gives { path, head, at(t), left(t), samples }: the path data of its line and of its head, the
 * point a share t of the way along, the unit vector to its left there, and points along it.
 */
export function arrow(points, width, shift = 0) {
  const [cx, cy] = unit(points[3][0] - points[0][0], points[3][1] - points[0][1]);
  const [p0, p1, p2, p3] = points.map(([x, y]) => [x + cy * shift, y - cx * shift]);
  const [sx, sy] = unit(p1[0] - p0[0], p1[1] - p0[1]);
  const [ex, ey] = unit(p3[0] - p2[0], p3[1] - p2[1]);
  const start = [p0[0] + sx * GAP, p0[1] + sy * GAP];
  const tip = [p3[0] - ex * GAP, p3[1] - ey * GAP];
  const end = [tip[0] - ex * ARROW, tip[1] - ey * ARROW];
  const curve = [start, p1, p2, end];
  const at = (t) => {
    const k = [(1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3];
    return [0, 1].map((d) => curve.reduce((sum, p, i) => sum + k[i] * p[d], 0));
  };
  const left = (t) => {
    const k = [-3 * (1 - t) ** 2, 3 * (1 - t) ** 2 - 6 * (1 - t) * t, 6 * (1 - t) * t - 3 * t ** 2, 3 * t ** 2];
    const [ux, uy] = unit(...[0, 1].map((d) => curve.reduce((sum, p, i) => sum + k[i] * p[d], 0)));
    return [uy, -ux];
  };
  const point = ([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`;
  const half = head(width);
  return {
    path: `M${point(start)}C${point(p1)} ${point(p2)} ${point(end)}`,
    head: `M${point(tip)}L${point([end[0] + ey * half, end[1] - ex * half])}L${point([end[0] - ey * half, end[1] + ex * half])}Z`,
    at,
    left,
    samples: Array.from({ length: 41 }, (_, i) => at(i / 40)),
  };
}

/**
 * Where an arrow's labels go: its share on one side and its wait on the other, the share above (or on
 * the left of an upright arrow) where it can be, each at the first of a few places along it that clears
 * the map's edges, the boxes in `taken` and the arrows (`marks`, as [x, y, radius]), with text as wide as
 * `measure(text)` gives. Failing that, or `together`, both on one side, on two lines, the left of travel
 * first. Failing that, the share alone; and if even that has no clear place, the share where it crosses
 * fewest arrows, but never over other text or off the map, or else nothing. Gives a list of
 * { lines, x, bounds }.
 */
export function place(texts, width, geometry, { width: w, height: h, taken, marks, measure }, { together = false } = {}) {
  // A box beside the arrow, a little further out if that clears it: inside a bend, the arrow curves
  // towards it.
  const box = (lines, t, side, also) => {
    const [nx, ny] = geometry.left(t);
    const boxWidth = Math.max(...lines.map((text) => measure(text))) + 8;
    const boxHeight = LINE * lines.length + 2;
    const [px, py] = geometry.at(t);
    let best = null;
    for (const extra of [0, 5, 10]) {
      const reach = width / 2 + 4 + extra + Math.abs(nx) * (boxWidth / 2) + Math.abs(ny) * (boxHeight / 2);
      const [cx, cy] = [px + side * nx * reach, py + side * ny * reach];
      const bounds = [cx - boxWidth / 2, cy - boxHeight / 2, cx + boxWidth / 2, cy + boxHeight / 2];
      const outside = bounds[0] < 0 || bounds[1] < 0 || bounds[2] > w || bounds[3] > h ? 1 : 0;
      const overlaps = [...taken, ...also].filter(([a, b, c, d]) => bounds[0] < c && a < bounds[2] && bounds[1] < d && b < bounds[3]).length;
      const crossings = marks.filter(([x, y, r]) => x > bounds[0] - r && x < bounds[2] + r && y > bounds[1] - r && y < bounds[3] + r).length;
      const clashes = outside + overlaps + crossings;
      if (!best || clashes < best.clashes) best = { lines, x: cx, bounds, clashes, overlaps: overlaps + outside };
      if (!clashes) break;
    }
    return best;
  };
  const along = [0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8];
  const on = (...sides) => sides.flatMap((side) => along.map((t) => [t, side]));
  let fallback = null;
  // The first of `places` where `lines` clear everything, and `also` too.
  const clear = (lines, places, also = []) => {
    for (const [t, side] of places) {
      const b = box(lines, t, side, also);
      if (!b.clashes) return b;
      if (lines.length === 1 && lines[0] === texts[0] && !b.overlaps && (!fallback || b.clashes < fallback.clashes)) fallback = b;
    }
    return null;
  };
  const [nx, ny] = geometry.left(0.5);
  const up = ny < -0.2 || (ny <= 0.2 && nx < 0) ? 1 : -1; // the side above, or on the left of an upright arrow
  if (!together && texts.length === 2) {
    for (const side of [up, -up]) {
      const share = clear([texts[0]], on(side));
      const wait = share && clear([texts[1]], on(-side), [share.bounds]);
      if (wait) return [share, wait];
    }
  }
  if (texts.length === 2) {
    const both = clear(texts, on(1, -1));
    if (both) return [both];
  }
  const share = clear([texts[0]], on(up, -up)) ?? fallback;
  return share ? [share] : [];
}
