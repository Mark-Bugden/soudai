// The Process map tab: how civil cases move between the stages, for the whole country or the court
// selected, beside the share of cases still waiting for a decision, and to become legally final, each
// month after filing.
//
// - The map: a node per stage (see journey.PLACES) and an arrow per move, its width the share of cases
//   that make the move at least once, the commonest labelled with their median wait. Each arrow bows to
//   its left, so a move and its reverse don't overlap. Hovering an arrow gives its share and the
//   quartiles of its wait; a hidden table gives every move to screen readers.
// - The curves: for the court, in the accent, against all courts, in the curve colour.
//
// Colours come from CSS classes (see demo.css), so a theme change needs no redraw.

import { h, s } from '../dom.js';
import * as describe from '../format.js';
import { PLACES, commonest, moves } from '../journey.js';
import { createTooltip } from '../tooltip.js';

const LABELLED = 0.02; // moves made by at least this share of cases are labelled with their wait
const DRAWN = 0.005; // moves made by fewer are left off the map, but stay in the hidden table
const MONTHS = 24; // months after filing on the curves
const CHARACTER = 6.6; // px, about the width of a character of a label, to keep labels apart
const NODE = 7; // px, a stage's radius
const BEND = 0.12; // how far an arrow bows, as a share of its length
const ARROW = 8; // px, the length of an arrowhead

export function createMap(host, data) {
  const meta = h('p', { class: 'sd-case-meta' });
  const key = h('p', { class: 'sd-note' }, 'Each arrow\'s width is the share of cases that make the move at least once, '
    + 'and the commonest are labelled with their median wait. Moves made by fewer than 0.5% of cases aren\'t drawn.');
  const mapSvg = s('svg', { class: 'sd-chart sd-flow', 'aria-hidden': 'true' });
  const mapBox = h('div', { class: 'sd-chart-box sd-map-box' }, mapSvg);
  const legend = h('p', { class: 'sd-legend' });
  const panels = ['decided', 'final'].map((which) => {
    const svg = s('svg', { class: 'sd-chart', 'aria-hidden': 'true' });
    const box = h('div', { class: 'sd-chart-box' }, svg);
    const title = h('p', { class: 'sd-cal-title' }, which === 'decided' ? 'Not yet decided' : 'Not yet legally final');
    return { which, svg, box, el: h('div', { class: 'sd-curve' }, title, box) };
  });
  const table = h('table', { class: 'sd-sr-only' });
  const el = h('div', { class: 'sd-map' },
    h('div', { class: 'sd-case' }, h('p', { class: 'sd-case-title' }, 'Process map'), meta),
    h('div', { class: 'sd-map-body' },
      h('div', { class: 'sd-map-flow' }, key, mapBox),
      h('div', { class: 'sd-curves' }, legend, ...panels.map((panel) => panel.el))),
    table);
  host.append(el);
  const mapTip = createTooltip(mapBox);
  const tips = panels.map((panel) => createTooltip(panel.box));
  let curves = null; // what the curves' crosshair needs

  function render({ court }) {
    const journey = data.journey(court);
    const all = data.journey(null);
    const route = commonest(journey, data.stages);
    meta.textContent = `${court ? court.name : 'All courts'}: ${describe.registered(journey)} in 2020–2025. `
      + `Commonest route: ${describe.route(route.stages)}, ${describe.share(route.share)} of cases.`;
    const list = moves(journey, data.stages);
    describeMoves(list);
    drawMap(journey, list);
    legend.replaceChildren(...(court
      ? [h('span', { class: 'sd-key sd-key-model' }), h('span', { class: 'sd-legend-name' }, court.area),
        h('span', { class: 'sd-key sd-key-diagonal' }), 'All courts']
      : []));
    curves = { court, journey, all, drawn: panels.map((panel) => drawCurve(panel, court ? journey : null, all)) };
    mapTip.hide();
    for (const tip of tips) tip.hide();
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

  function drawMap(journey, list) {
    const width = mapBox.clientWidth;
    const height = mapBox.clientHeight;
    size(mapSvg, width, height);
    if (width < 120 || height < 120) {
      mapSvg.replaceChildren();
      return;
    }
    const pad = { left: 12, right: 12, top: 38, bottom: 34 };
    const at = (stage) => [pad.left + PLACES[stage][0] * (width - pad.left - pad.right), pad.top + PLACES[stage][1] * (height - pad.top - pad.bottom)];
    const widest = Math.max(8, Math.min(24, Math.min(width, height) * 0.05));
    const stroke = (share) => 1 + (widest - 1) * share;

    const edges = s('g', { class: 'sd-edges' });
    const candidates = []; // { text, x, y, share }, labels for the commonest moves
    const hits = [];
    // The rarest first, so the commonest are drawn on top; the hit areas the other way round, so a thin
    // arrow under a thick one can still be found.
    for (const move of [...list].reverse()) {
      if (move.share < DRAWN) continue;
      const w = stroke(move.share);
      const geometry = arrow(at(move.from), at(move.to), w);
      const group = s('g', { class: 'sd-edge' },
        s('path', { class: 'sd-edge-line', d: geometry.path, 'stroke-width': w.toFixed(2) }),
        s('path', { class: 'sd-edge-head', d: geometry.head }));
      edges.append(group);
      const hit = s('path', { class: 'sd-edge-hit', d: geometry.path, 'stroke-width': Math.max(14, w + 8).toFixed(1) });
      hit.addEventListener('pointerenter', () => showMove(move, group, geometry.label));
      hit.addEventListener('pointerleave', () => hideMove(group));
      hits.unshift(hit);
      if (move.share >= LABELLED && move.wait) {
        candidates.push({ text: describe.wait(move.wait[1]), x: geometry.label[0], y: geometry.label[1], share: move.share });
      }
    }
    const taken = []; // the boxes of what's labelled so far: the stages, then the moves'

    const nodes = s('g', { class: 'sd-nodes' });
    data.stages.forEach((stage, i) => {
      if (stage === 'closed' && !list.some((move) => move.to === 'closed' && move.share >= DRAWN)) return;
      const [x, y] = at(stage);
      const above = PLACES[stage][1] < 0.3;
      const anchor = PLACES[stage][0] < 0.1 ? 'start' : PLACES[stage][0] > 0.9 ? 'end' : 'middle';
      const tx = anchor === 'start' ? x - NODE : anchor === 'end' ? x + NODE : x;
      const reached = i < journey.stages.length ? journey.stages[i] : null;
      const name = describe.STAGES[stage];
      // On narrow maps the stages are close together, so their shares go without "of cases".
      const reachedText = reached === null ? null : `${reached > 0.9995 ? '100%' : describe.share(reached)}${width < 560 ? '' : ' of cases'}`;
      const lines = [name, ...(reachedText ? [reachedText] : [])];
      const top = above ? y - NODE - 6 - 14 * lines.length : y + NODE + 2;
      nodes.append(s('circle', { class: 'sd-node', cx: x, cy: y, r: NODE }));
      lines.forEach((line, j) => {
        nodes.append(s('text', { class: j ? 'sd-node-share' : 'sd-node-label', x: tx, y: top + 12 + 14 * j, 'text-anchor': anchor }, line));
      });
      const wide = Math.max(...lines.map((line) => line.length)) * CHARACTER;
      const x0 = anchor === 'start' ? tx : anchor === 'end' ? tx - wide : tx - wide / 2;
      taken.push([x - NODE, y - NODE, x + NODE, y + NODE], [x0, top, x0 + wide, top + 14 * lines.length + 2]);
    });
    // The moves' labels, the commonest first, each left out if it would overlap one already placed.
    const labels = [];
    for (const label of candidates.sort((a, b) => b.share - a.share)) {
      const half = (label.text.length * CHARACTER) / 2 + 2;
      const box = [label.x - half, label.y - 8, label.x + half, label.y + 8];
      if (taken.some(([a, b, c, d]) => box[0] < c && a < box[2] && box[1] < d && b < box[3])) continue;
      taken.push(box);
      labels.push(s('text', { class: 'sd-edge-label', x: label.x, y: label.y, dy: '0.32em', 'text-anchor': 'middle' }, label.text));
    }
    mapSvg.replaceChildren(edges, ...labels, nodes, ...hits);
  }

  function showMove(move, group, [x, y]) {
    mapSvg.classList.add('has-hover');
    group.classList.add('is-hover');
    const lines = [`${describe.STAGES[move.from]} → ${describe.STAGES[move.to]}`, `${describe.share(move.share)} of cases`];
    if (move.wait) {
      lines.push(`Median wait: ${describe.wait(move.wait[1])}`,
        `Half waited ${describe.count(move.wait[0])} to ${describe.days(move.wait[2])}`);
    } else {
      lines.push('Too few sampled cases for a wait');
    }
    mapTip.show(lines, { x, y });
  }

  function hideMove(group) {
    mapSvg.classList.remove('has-hover');
    group.classList.remove('is-hover');
    mapTip.hide();
  }

  /** One of the curves: the court's share still waiting, if a court is selected, against all courts'. */
  function drawCurve(panel, journey, all) {
    const width = panel.box.clientWidth;
    const height = panel.box.clientHeight;
    size(panel.svg, width, height);
    if (width < 80 || height < 60) {
      panel.svg.replaceChildren();
      return null;
    }
    const margin = { top: 6, right: 10, bottom: 22, left: 40 };
    const x = (month) => margin.left + (month / MONTHS) * (width - margin.left - margin.right);
    const y = (p) => height - margin.bottom - p * (height - margin.top - margin.bottom);
    const key = panel.which === 'decided' ? 'notDecided' : 'notFinal';
    const line = (values) => values.slice(0, MONTHS + 1).map((v, m) => `${m ? 'L' : 'M'}${x(m).toFixed(1)},${y(v).toFixed(1)}`).join('');
    const nodes = [];
    for (const p of [0, 0.5, 1]) {
      nodes.push(
        s('line', { class: p === 0 ? 'sd-axis-line' : 'sd-grid', x1: x(0), x2: x(MONTHS), y1: y(p), y2: y(p) }),
        s('text', { class: 'sd-tick', x: margin.left - 8, y: y(p), dy: '0.32em', 'text-anchor': 'end' }, `${p * 100}%`),
      );
    }
    const step = x(6) - x(0) >= 28 ? 6 : 12;
    for (let m = 0; m <= MONTHS; m += step) {
      nodes.push(s('text', { class: 'sd-tick', x: x(m), y: height - 6, 'text-anchor': 'middle' }, String(m)));
    }
    nodes.push(s('path', { class: journey ? 'sd-curve-all' : 'sd-forecast-line', d: line(all[key]) }));
    if (journey) nodes.push(s('path', { class: 'sd-forecast-line', d: line(journey[key]) }));
    const cross = s('g', { class: 'sd-cross' });
    nodes.push(cross);
    panel.svg.replaceChildren(...nodes);
    return { x, y, key, cross, left: margin.left, right: width - margin.right };
  }

  // The curves' crosshair: the nearest month, in both panels, with the values in a tooltip.
  panels.forEach((panel, i) => {
    panel.svg.addEventListener('pointermove', (event) => {
      const drawn = curves?.drawn[i];
      if (!drawn) return;
      const box = panel.svg.getBoundingClientRect();
      const month = Math.round(((event.clientX - box.left - drawn.left) / (drawn.right - drawn.left)) * MONTHS);
      if (month < 0 || month > MONTHS) {
        clearCross();
        return;
      }
      const series = curves.court ? [curves.journey, curves.all] : [curves.all];
      curves.drawn.forEach((other) => {
        if (!other) return;
        other.cross.replaceChildren(
          s('line', { class: 'sd-cross-line', x1: other.x(month), x2: other.x(month), y1: other.y(1), y2: other.y(0) }),
          ...series.map((journey, j) => s('circle', { class: j === 0 ? 'sd-forecast-dot' : 'sd-curve-dot', cx: other.x(month), cy: other.y(journey[other.key][month]), r: 4 })),
        );
      });
      const name = curves.court ? curves.court.area : 'All courts';
      const what = drawn.key === 'notDecided' ? 'not yet decided' : 'not yet legally final';
      const lines = [month ? `${describe.months(month)} after filing` : 'At filing',
        `${name}: ${describe.percent(curves.journey[drawn.key][month])} ${what}`];
      if (curves.court) lines.push(`All courts: ${describe.percent(curves.all[drawn.key][month])}`);
      tips[i].show(lines, { x: drawn.x(month), y: drawn.y(curves.journey[drawn.key][month]) - 4 });
    });
    panel.svg.addEventListener('pointerleave', clearCross);
  });

  function clearCross() {
    for (const drawn of curves?.drawn ?? []) drawn?.cross.replaceChildren();
    for (const tip of tips) tip.hide();
  }

  return {
    render,
    destroy() {
      mapTip.destroy();
      for (const tip of tips) tip.destroy();
      el.remove();
    },
  };
}

function size(svg, width, height) {
  svg.setAttribute('width', width);
  svg.setAttribute('height', height);
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
}

/**
 * An arrow from one stage to another, bowing to its left: { path, head, label }, the curve's path data,
 * its head's, and where to put its label, just outside the bow. It starts and ends clear of the stages.
 */
export function arrow([x0, y0], [x1, y1], width) {
  const dx = x1 - x0;
  const dy = y1 - y0;
  // The control point: the midpoint, moved to the left of the direction of travel (y runs down).
  const cx = (x0 + x1) / 2 + dy * BEND * 2;
  const cy = (y0 + y1) / 2 - dx * BEND * 2;
  const unit = (ax, ay) => {
    const length = Math.hypot(ax, ay) || 1;
    return [ax / length, ay / length];
  };
  const [sx, sy] = unit(cx - x0, cy - y0);
  const [ex, ey] = unit(x1 - cx, y1 - cy);
  const gap = NODE + 3;
  const start = [x0 + sx * gap, y0 + sy * gap];
  const tip = [x1 - ex * gap, y1 - ey * gap];
  const end = [tip[0] - ex * ARROW, tip[1] - ey * ARROW];
  const half = Math.max(4.5, width / 2 + 2.5);
  const head = `M${tip[0].toFixed(1)},${tip[1].toFixed(1)}L${(end[0] - ey * half).toFixed(1)},${(end[1] + ex * half).toFixed(1)}`
    + `L${(end[0] + ey * half).toFixed(1)},${(end[1] - ex * half).toFixed(1)}Z`;
  // The curve's midpoint, and the direction it bows in.
  const mx = 0.25 * x0 + 0.5 * cx + 0.25 * x1;
  const my = 0.25 * y0 + 0.5 * cy + 0.25 * y1;
  const [bx, by] = unit(cx - (x0 + x1) / 2, cy - (y0 + y1) / 2);
  const out = width / 2 + 9;
  return {
    path: `M${start[0].toFixed(1)},${start[1].toFixed(1)}Q${cx.toFixed(1)},${cy.toFixed(1)} ${end[0].toFixed(1)},${end[1].toFixed(1)}`,
    head,
    label: [mx + bx * out, my + by * out],
  };
}
