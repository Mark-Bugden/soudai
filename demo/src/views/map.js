// The Process map tab: how civil cases move between the stages, for the whole country or the court
// selected, beside the share of cases legally final each month after filing and the most common routes.
//
// - The map: a node per stage (see journey.PLACES) and an arrow per move made by at least 2% of cases,
//   its width that share. Arrows join only stages next to each other: straight along the rows, in an
//   arc over the hearing from filing to a decision, and along arcs below the row through suspensions,
//   revivals and appeals. A move and its reverse sit side by side. Each arrow has its share on one side
//   and its median wait on the other, where they're clear of everything else and plainly its own;
//   where the map is too crowded for that, they show only while the arrow is hovered. Hovering an arrow
//   dims everything but it, its labels and its two stages; hovering a stage, everything but its arrows,
//   the stages they join and the labels that fit. A hidden table gives every move to screen readers.
// - The curve: the court's, in the accent, against all courts', in the curve colour. Hovering it reads
//   the nearest month's values off the y axis.
// - The routes: those taken by more than 5% of cases, each with a bar for its share, then all others.
//
// Colours come from CSS classes (see demo.css), so a theme change needs no redraw.

import { h, s } from '../dom.js';
import * as describe from '../format.js';
import { ARCS, DRAWN, PLACES, legallyFinal, moves, mostCommon, shape, split } from '../journey.js';
import { clearReading, showReading } from '../reading.js';

const MONTHS = 24; // months after filing on the curve
const LINE = 15; // px, a label's line height
const NODE = 7; // px, a stage's radius
const GAP = NODE + 3; // px between a stage and the arrows that leave or reach it
const ARROW = 8; // px, the length of an arrowhead
const NARROW = 480; // px: on a map narrower than this, a stage's name can take two lines
const TILT = 0.47; // the slope at which an arc below the row reaches its bottom stage, about 25°
const CLEAR = 40; // px: a label always shown is this much nearer its own arrow than any other, less 2 px
                  // for each px of the arrow's width, down to 12: a thick arrow claims its labels more plainly
const SPACE = 8; // px: and at least this far from any other arrow's label
const SLANT = 7; // degrees: on a diagonal arrow, labels go where it runs within this of 45°

export function createMap(host, data) {
  const meta = h('p', { class: 'sd-case-meta' });
  const mapSvg = s('svg', { class: 'sd-chart sd-flow', 'aria-hidden': 'true' });
  const mapBox = h('div', { class: 'sd-chart-box sd-map-box' }, mapSvg);
  const rest = h('p', { class: 'sd-note' });
  const legend = h('p', { class: 'sd-legend' });
  const curveSvg = s('svg', { class: 'sd-chart', 'aria-hidden': 'true' });
  const curveBox = h('div', { class: 'sd-chart-box sd-curve-box' }, curveSvg);
  const routeList = h('ol', { class: 'sd-routes', 'aria-labelledby': 'sd-routes-title' });
  const table = h('table', { class: 'sd-sr-only' });
  const el = h('div', { class: 'sd-map' },
    h('div', { class: 'sd-map-flow' },
      h('div', { class: 'sd-case' }, h('p', { class: 'sd-case-title' }, 'Process map'), meta), mapBox, rest),
    h('div', { class: 'sd-curves' },
      h('div', { class: 'sd-half' }, h('p', { class: 'sd-cal-title' }, 'Share of cases legally final, by months after filing'), legend, curveBox),
      h('div', { class: 'sd-half' }, h('p', { class: 'sd-cal-title', id: 'sd-routes-title' }, 'Most common routes'), routeList)),
    table);
  host.append(el);
  let curve = null; // what reading the curve needs
  let lit = null; // what's lit on the map: { show, cover }
  const ruler = document.createElement('canvas').getContext('2d');

  /** The width of a label's text in px, in the map's font: its 12px, bold for a stage's name. */
  function measure(text, bold = false) {
    ruler.font = `${bold ? 600 : 400} 12px ${getComputedStyle(mapSvg).fontFamily}`;
    return ruler.measureText(text).width;
  }

  /** An arrow's label's width, bold as it is when lit, so that it fits then too. */
  const measureLit = (text) => measure(text, true);

  function render({ court }) {
    const journey = data.journey(court);
    meta.textContent = 'The share of cases making each move, and the median wait between stages.';
    const list = moves(journey, data.stages);
    const { drawn, rest: left } = split(list);
    describeMoves(list);
    rest.textContent = describe.notShown(left, DRAWN);
    legend.hidden = !court;
    legend.replaceChildren(...(court
      ? [h('span', { class: 'sd-key sd-key-model' }), h('span', { class: 'sd-legend-name' }, court.area),
        h('span', { class: 'sd-key sd-key-diagonal' }), 'All courts']
      : []));
    listRoutes(journey);
    drawMap(journey, drawn);
    curve = drawCurve(court ? legallyFinal(journey) : null, legallyFinal(data.journey(null)));
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

  /**
   * The routes taken by more than 5% of cases, each with a bar as long as its share, and then all the
   * others together, last whatever their share. If they don't fit, the rarest listed join the others.
   */
  function listRoutes(journey) {
    const { list, others } = mostCommon(journey, data.stages);
    const row = (name, share) => {
      const bar = h('span', { class: 'sd-route-bar' });
      bar.style.width = `${(share * 100).toFixed(2)}%`;
      return h('li', { class: 'sd-route' },
        h('span', { class: 'sd-route-name' }, name),
        h('span', { class: 'sd-route-share' }, describe.share(share)),
        h('span', { class: 'sd-route-track' }, bar));
    };
    for (let n = list.length; n >= Math.min(1, list.length); n--) {
      const folded = others + list.slice(n).reduce((sum, route) => sum + route.share, 0);
      routeList.replaceChildren(...list.slice(0, n).map((route) => row(describe.routeText(route), route.share)),
        ...(folded >= 0.0005 ? [row('Others', folded)] : []));
      if (routeList.scrollHeight <= routeList.clientHeight + 1) break;
    }
  }

  function drawMap(journey, drawn) {
    const width = mapBox.clientWidth;
    const height = mapBox.clientHeight;
    size(mapSvg, width, height);
    lit = null;
    mapSvg.classList.remove('has-hover');
    if (width < 160 || height < 120) {
      mapSvg.replaceChildren();
      return;
    }
    const shares = new Map(data.stages.map((stage, i) => [stage, i < journey.stages.length ? journey.stages[i] : null]));
    const shareText = (stage) => (shares.get(stage) === null ? null : (shares.get(stage) > 0.9995 ? '100%' : describe.share(shares.get(stage))));
    const widest = Math.max(8, Math.min(24, Math.min(width, height) * 0.05));
    const stroke = (share) => 1 + (widest - 1) * share;
    const overWidth = stroke(drawn.find((move) => shape(move.from, move.to) === 'over')?.share ?? 0);

    // The rows. The arc over the hearing rises about a fifth of its span, up to 1.3 times that, and the
    // arcs below dip half of theirs, up to 1.8 times that, as far as the height allows, and the drawing
    // is centred in it; on a narrow map, up to 2 and 3 times, to make room for the labels. The arc over
    // the hearing always clears the hearing's label, and the arcs below leave room for theirs.
    const pad = {
      left: Math.max(measure('Filed', true), measure(shareText('filed') ?? '')) + NODE + 12,
      right: NODE + 4,
      top: LINE + 8 + overWidth / 2,
      bottom: NODE + 4 + 2 * LINE + 2,
    };
    const inner = width - pad.left - pad.right;
    const room = height - pad.top - pad.bottom;
    const least = { lift: NODE + 2 * LINE + 12 + overWidth / 2, depth: 2 * NODE + 2 * LINE + 4 };
    const want = { lift: 0.22 * (PLACES.decided[0] - PLACES.filed[0]) * inner, depth: 0.5 * (PLACES.decided[0] - PLACES.hearing[0]) * inner };
    const most = inner < 400 ? { lift: 2, depth: 3 } : { lift: 1.3, depth: 1.8 };
    const lift = Math.max(least.lift, want.lift * Math.min(most.lift, room / (want.lift + want.depth)));
    const depth = Math.max(least.depth, Math.min(want.depth * most.depth, room - lift));
    const top = pad.top + Math.max(0, (room - lift - depth) / 2) + lift;
    const at = (stage) => [pad.left + PLACES[stage][0] * inner, top + PLACES[stage][1] * depth];

    // What labels must keep clear of: the stages and their labels, the arrows, and the other labels.
    const taken = [];
    const stages = new Map();
    const stageHits = new Map();
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
      stages.set(stage, s('g', { class: 'sd-stage' }, s('circle', { class: 'sd-node', cx: x, cy: y, r: NODE }),
        ...lines.map((text, j) => s('text', { class: j < name.length ? 'sd-node-label' : 'sd-node-share', x: tx, y: box[1] + LINE * j + 11, 'text-anchor': anchor }, text))));
      stageHits.set(stage, s('g', { class: 'sd-stage-hit' }, s('circle', { cx: x, cy: y, r: NODE + 4 }),
        s('rect', { x: box[0], y: box[1], width: box[2] - box[0], height: box[3] - box[1] })));
      taken.push([x - NODE, y - NODE, x + NODE, y + NODE], box);
    }
    const stageBoxes = [...taken];

    // The arrows, a move and its reverse (its twin) side by side.
    const arrows = drawn.map((move, id) => {
      const w = stroke(move.share);
      const twin = drawn.findIndex((other) => other.from === move.to && other.to === move.from);
      const points = route(move.from, move.to, at, { lift });
      return { id, move, w, twin: twin < 0 ? null : twin, geometry: arrow(points, w, twin < 0 ? 0 : head(w) + 1.5) };
    });
    const marks = arrows.flatMap(({ id, w, geometry }) => geometry.samples.map(([x, y]) => [x, y, w / 2 + 2, id]));

    // The labels, the commonest arrow's first. Each arrow's are always shown where they clear everything
    // placed so far, keep SPACE px from other arrows' labels and are plainly its own; the rest show only
    // while their arrow is hovered, as clear of the labels always shown as they can be, and hide those
    // they can't clear.
    const overlap = (a, b) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
    for (const a of arrows) {
      const space = { width, height, taken, marks, measure: measureLit, own: a.id, twin: a.twin };
      a.boxes = place(describe.moveLabel(a.move), a.w, a.geometry, space, { together: a.twin !== null });
      a.extra = !a.boxes.length;
      taken.push(...a.boxes.map(({ bounds: [x0, y0, x1, y1] }) => [x0 - SPACE, y0 - SPACE, x1 + SPACE, y1 + SPACE]));
    }
    for (const a of arrows.filter(({ extra }) => extra)) {
      const space = { width, height, taken, marks, measure: measureLit, own: a.id, twin: a.twin };
      const options = { together: a.twin !== null, sure: false };
      a.boxes = [place(describe.moveLabel(a.move), a.w, a.geometry, space, options),
        () => place(describe.moveLabel(a.move), a.w, a.geometry, { ...space, taken: stageBoxes }, options),
        () => place(describe.moveLabel(a.move), a.w, a.geometry, { ...space, taken: stageBoxes, marks: marks.filter(([, , , id]) => id === a.id) }, { ...options, fallback: true }),
      ].reduce((found, next) => (found.length ? found : next()));
    }
    for (const a of arrows) {
      a.label = s('g', { class: a.extra ? 'sd-edge-label is-extra' : 'sd-edge-label' }, ...a.boxes.map((box) => s('text', { 'text-anchor': 'middle' },
        ...box.lines.map((text, j) => s('tspan', { x: box.x, y: box.bounds[1] + LINE * j + 12 }, text)))));
      a.covers = a.extra ? arrows.filter((b) => !b.extra && b.boxes.some((box) => a.boxes.some((mine) => overlap(box.bounds, mine.bounds)))).map((b) => b.label) : [];
    }

    // The rarest first, so the commonest are drawn on top; the hit areas the other way round, so a thin
    // arrow under a thick one can still be found. The stages' hit areas go over the arrows'.
    const edges = s('g', { class: 'sd-edges' });
    const hits = [];
    for (const a of [...arrows].reverse()) {
      a.group = s('g', { class: 'sd-edge' },
        s('path', { class: 'sd-edge-line', d: a.geometry.path, 'stroke-width': a.w.toFixed(2) }),
        s('path', { class: 'sd-edge-head', d: a.geometry.head }));
      edges.append(a.group);
      const hit = s('path', { class: 'sd-edge-hit', d: a.geometry.path, 'stroke-width': Math.max(12, a.w + 6).toFixed(1) });
      hover(hit, { show: [a.group, a.label, stages.get(a.move.from), stages.get(a.move.to)], cover: a.covers });
      hits.unshift(hit);
    }

    // A stage lights its arrows, the stages they join, and the arrows' labels: those always shown, then
    // those shown on hover where they clear the rest and are plainly their own among the arrows lit.
    for (const [stage, hit] of stageHits) {
      const mine = arrows.filter(({ move }) => move.from === stage || move.to === stage);
      const ids = new Set(mine.map(({ id }) => id));
      const near = marks.filter(([, , , id]) => ids.has(id));
      const show = [stages.get(stage), ...mine.flatMap(({ move, group }) => [group, stages.get(move.from === stage ? move.to : move.from)])];
      const used = mine.filter(({ extra }) => !extra).flatMap(({ boxes }) => boxes.map((box) => box.bounds));
      const cover = [];
      show.push(...mine.filter(({ extra }) => !extra).map(({ label }) => label));
      for (const a of mine.filter(({ extra, boxes }) => extra && boxes.length)) {
        const fits = a.boxes.every(({ bounds }) => !used.some((box) => overlap(box, bounds)) && nearer(bounds, near, a.id, a.twin));
        if (!fits) continue;
        show.push(a.label);
        used.push(...a.boxes.map((box) => box.bounds));
        cover.push(...a.covers);
      }
      hover(hit, { show, cover });
    }
    mapSvg.replaceChildren(edges, ...arrows.map(({ label }) => label), ...stages.values(), ...hits, ...stageHits.values());
  }

  /** Hovering, or on a touch screen tapping, lights what `set` shows and dims the rest of the map. */
  function hover(hit, set) {
    hit.addEventListener('pointerenter', (event) => event.pointerType === 'touch' || light(set));
    hit.addEventListener('pointerleave', (event) => event.pointerType === 'touch' || light(null));
    hit.addEventListener('pointerup', (event) => event.pointerType === 'touch' && light(lit === set ? null : set));
  }

  function light(set) {
    if (lit) toggle(lit, false);
    lit = set;
    if (lit) toggle(lit, true);
    mapSvg.classList.toggle('has-hover', Boolean(lit));
  }

  function toggle({ show, cover }, on) {
    for (const node of show) node.classList.toggle('is-hover', on);
    for (const node of cover) node.classList.toggle('is-covered', on);
  }

  // A tap away from the arrows and stages puts the map back.
  mapSvg.addEventListener('pointerup', (event) => {
    if (event.pointerType === 'touch' && !event.target.closest('.sd-edge-hit, .sd-stage-hit')) light(null);
  });

  /** The curve: the court's share legally final, if a court is selected, against all courts'. */
  function drawCurve(values, all) {
    const width = curveBox.clientWidth;
    const height = curveBox.clientHeight;
    size(curveSvg, width, height);
    if (width < 80 || height < 60) {
      curveSvg.replaceChildren();
      return null;
    }
    const margin = { top: 8, right: 10, bottom: 40, left: 40 };
    const x = (month) => margin.left + (month / MONTHS) * (width - margin.left - margin.right);
    const y = (p) => height - margin.bottom - p * (height - margin.top - margin.bottom);
    const path = (series) => series.slice(0, MONTHS + 1).map((v, m) => `${m ? 'L' : 'M'}${x(m).toFixed(1)},${y(v).toFixed(1)}`).join('');
    const nodes = [];
    const ticks = [];
    for (const p of [0, 0.5, 1]) {
      const tick = s('text', { class: 'sd-tick', x: margin.left - 8, y: y(p), dy: '0.32em', 'text-anchor': 'end' }, `${p * 100}%`);
      ticks.push({ tick, at: y(p) });
      nodes.push(s('line', { class: p === 0 ? 'sd-axis-line' : 'sd-grid', x1: x(0), x2: x(MONTHS), y1: y(p), y2: y(p) }), tick);
    }
    // Ticks every 3 months, longer every 6, which are labelled (every 12 if they'd be cramped).
    const step = x(6) - x(0) >= 28 ? 6 : 12;
    for (let m = 0; m <= MONTHS; m += 3) {
      nodes.push(s('line', { class: 'sd-axis-tick', x1: x(m), x2: x(m), y1: y(0), y2: y(0) + (m % 6 ? 3 : 6) }));
      if (m % step === 0) nodes.push(s('text', { class: 'sd-tick', x: x(m), y: height - 21, 'text-anchor': 'middle' }, String(m)));
    }
    nodes.push(s('text', { class: 'sd-tick', x: x(MONTHS), y: height - 4, 'text-anchor': 'end' }, 'Months after filing'));
    nodes.push(s('path', { class: values ? 'sd-curve-all' : 'sd-forecast-line', d: path(all) }));
    if (values) nodes.push(s('path', { class: 'sd-forecast-line', d: path(values) }));
    const reading = s('g', { class: 'sd-reading' });
    nodes.push(reading);
    curveSvg.replaceChildren(...nodes);
    const lines = values ? [{ series: values, dot: 'sd-forecast-dot' }, { series: all, dot: 'sd-curve-dot' }] : [{ series: all, dot: 'sd-forecast-dot' }];
    return { lines, x, y, reading, ticks, left: margin.left, right: width - margin.right };
  }

  // Reading the curve off its y axis, at the nearest month.
  curveSvg.addEventListener('pointermove', (event) => {
    if (!curve) return;
    const box = curveSvg.getBoundingClientRect();
    const month = Math.round(((event.clientX - box.left - curve.left) / (curve.right - curve.left)) * MONTHS);
    if (month < 0 || month > MONTHS) {
      clear();
      return;
    }
    const { x, y, lines, ticks, left } = curve;
    showReading(curve.reading, {
      x: x(month),
      top: y(1),
      bottom: y(0),
      left,
      values: lines.map(({ series, dot }) => ({ cx: x(month), at: y(series[month]), text: describe.percent(series[month]), dot })),
      ticks,
    });
  });
  curveSvg.addEventListener('pointerleave', clear);

  function clear() {
    if (curve) clearReading(curve.reading, curve.ticks);
  }

  return {
    render,
    destroy() {
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

/**
 * The curve a move follows on the map, between its stages' centres (`at(stage)`), as a cubic Bézier's
 * four points: straight for a line; for the arc over the hearing, rising `lift` px at its middle; or
 * along the arc below the row whose bottom is a suspension, a revival or an appeal, leaving the row
 * steeply and reaching the bottom at a slope of TILT, so that a line along the bottom row stays clear.
 */
export function route(from, to, at, { lift }) {
  const [p, q] = [at(from), at(to)];
  const kind = shape(from, to);
  if (kind === 'line') return [p, mix(p, q, 1 / 3), mix(p, q, 2 / 3), q];
  if (kind === 'over') {
    const rise = lift / 0.75; // a cubic's middle reaches 3/4 of the way to its control points
    return [p, [p[0] + (q[0] - p[0]) / 4, p[1] - rise], [q[0] - (q[0] - p[0]) / 4, q[1] - rise], q];
  }
  // From the row down to the bottom of the arc, then the other way if the move goes up.
  const bottom = ARCS[from] ? from : to;
  const [r, b] = [at(bottom === to ? from : to), at(bottom)];
  const dx = b[0] - r[0];
  const down = [r, [r[0] + dx / 4, r[1] + (2 / 3) * (b[1] - r[1])], [b[0] - (3 / 8) * dx, b[1] - TILT * (3 / 8) * Math.abs(dx)], b];
  return bottom === to ? down : [...down].reverse();
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
 * Whether a label's box is plainly the arrow `own`'s: nearer it than any other arrow but its reverse
 * (`twin`), by CLEAR px beside a hairline and less beside a wider arrow, among points along the arrows
 * (`marks`, as [x, y, radius, arrow], the radius 2 px more than half the arrow's width).
 */
export function nearer(bounds, marks, own, twin = null) {
  let mine = Infinity;
  let other = Infinity;
  let width = 0;
  for (const [x, y, r, id] of marks) {
    const d = Math.hypot(Math.max(bounds[0] - x, 0, x - bounds[2]), Math.max(bounds[1] - y, 0, y - bounds[3])) - r;
    if (id === own) {
      mine = Math.min(mine, d);
      width = 2 * (r - 2);
    } else if (id !== twin) other = Math.min(other, d);
  }
  return other >= mine + Math.max(12, CLEAR - 2 * width);
}

/**
 * Where an arrow's labels go: its share on one side and its wait directly across from it, the share above
 * (or on the left of an upright arrow) where it can be, at the first of a few places along it where both
 * clear the map's edges, the boxes in `taken` and the arrows (`marks`, as [x, y, radius, arrow]), with
 * text as wide as `measure(text)` gives, and, if `sure`, are plainly the arrow `own`'s (see nearer). The
 * places are near the middle, or on a diagonal arrow where it runs within SLANT of 45°, so the two labels
 * sit diagonally across it. Failing that, or `together`, both on one side, on two lines, the left of
 * travel first, but not on a diagonal arrow alone. Failing that, nothing; or with `fallback`, the share
 * alone where it crosses fewest arrows, but never over other text or off the map. Gives a list of
 * { lines, x, bounds }.
 */
export function place(texts, width, geometry, { width: w, height: h, taken, marks, measure, own = null, twin = null },
  { together = false, sure = true, fallback = false } = {}) {
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
      const unclear = sure && !nearer(bounds, marks, own, twin) ? 1 : 0;
      const clashes = outside + overlaps + crossings + unclear;
      if (!best || clashes < best.clashes) best = { lines, x: cx, bounds, clashes, overlaps: overlaps + outside };
      if (!clashes) break;
    }
    return best;
  };
  const degrees = (x, y) => (Math.atan2(Math.abs(y), Math.abs(x)) * 180) / Math.PI;
  const [a, b] = [geometry.at(0), geometry.at(1)];
  const diagonal = Math.abs(degrees(b[0] - a[0], b[1] - a[1]) - 45) < 35;
  const off = (t) => Math.abs(degrees(geometry.left(t)[1], geometry.left(t)[0]) - 45); // the arrow's slope there, from 45°
  const slanted = Array.from({ length: 15 }, (_, i) => 0.15 + i * 0.05).sort((p, q) => off(p) - off(q));
  const along = diagonal
    ? slanted.filter((t, i) => off(t) <= SLANT || i < 2)
    : [0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8];
  const on = (...sides) => sides.flatMap((side) => along.map((t) => [t, side]));
  let least = null;
  // The first of `places` where `lines` clear everything, and `also` too.
  const clear = (lines, places, also = []) => {
    for (const [t, side] of places) {
      const b = box(lines, t, side, also);
      if (!b.clashes) return b;
      if (lines.length === 1 && lines[0] === texts[0] && !b.overlaps && (!least || b.clashes < least.clashes)) least = b;
    }
    return null;
  };
  const [nx, ny] = geometry.left(0.5);
  const up = ny < -0.2 || (ny <= 0.2 && nx < 0) ? 1 : -1; // the side above, or on the left of an upright arrow
  if (!together && texts.length === 2) {
    for (const side of [up, -up]) {
      for (const t of along) {
        const share = box([texts[0]], t, side, []);
        const wait = !share.clashes && box([texts[1]], t, -side, [share.bounds]);
        if (wait && !wait.clashes) return [share, wait];
      }
    }
  }
  if (texts.length === 2 && (together || !diagonal)) {
    const both = clear(texts, on(1, -1));
    if (both) return [both];
  }
  const share = clear([texts[0]], on(up, -up));
  if (share && texts.length === 1) return [share];
  return fallback && (share ?? least) ? [share ?? least] : [];
}
