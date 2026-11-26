// The Performance tab: how well the model does on the cases registered in 2024–2025, which it never
// trained on, over all courts.
//
// - Calibration: for each band of 10 points, the model's mean forecast that a case is legally final
//   within the months chosen in the rail, against the share of those cases that were, each dot sized by
//   its share of the forecasts, with the diagonal where the two agree. Hovering a dot reads it.
// - Ranking: how often the model and three simpler methods put two cases in the order they ended
//   (concordance), for forecasts made at filing and 1, 3, 6 and 12 months after. The model is in the
//   accent and the others in the curve colour, each named at its end. Hovering reads a landmark.
//
// Hidden tables give both to screen readers. Colours come from CSS classes (see demo.css), so a theme
// change needs no redraw.

import { h, s } from '../dom.js';
import * as describe from '../format.js';
import { BINS, LANDMARKS, MODEL, calibration, counts, gap, ranking } from '../performance.js';
import { createTooltip } from '../tooltip.js';
import { spread } from './map.js';

const REACH = 16; // px from a dot within which the pointer finds it
const LINE = 15; // px between the names at the ends of the ranking's lines
const RANGE = [0.5, 0.8]; // the ranking's axis, from a coin toss
const DOT = 4; // px, a landmark's dot on the ranking

export function createPerformance(host, data) {
  const { forecasts, cases } = counts(data);
  const lines = ranking(data);
  const model = lines.find((line) => line.key === MODEL);

  const calTitle = h('p', { class: 'sd-cal-title' });
  const calNote = h('p', { class: 'sd-note' });
  const calSvg = s('svg', { class: 'sd-chart', 'aria-hidden': 'true' });
  const calBox = h('div', { class: 'sd-chart-box sd-perf-box' }, calSvg);
  const rankSvg = s('svg', { class: 'sd-chart', 'aria-hidden': 'true' });
  const rankBox = h('div', { class: 'sd-chart-box sd-perf-box' }, rankSvg);
  const calTable = h('table', { class: 'sd-sr-only' });
  const el = h('div', { class: 'sd-perf' },
    h('div', { class: 'sd-case' },
      h('p', { class: 'sd-case-title' }, 'How well the model does'),
      h('p', { class: 'sd-case-meta' },
        `Its ${describe.count(forecasts)} forecasts for the ${describe.count(cases)} sampled cases registered in 2024–2025, made `
        + 'at filing and 1, 3, 6 and 12 months after, against what happened. It was trained on cases registered in 2020–2023.')),
    h('div', { class: 'sd-perf-body' },
      h('div', { class: 'sd-half' }, calTitle, calNote, calBox),
      h('div', { class: 'sd-half' },
        h('p', { class: 'sd-cal-title' }, 'Which of two cases ends first'),
        h('p', { class: 'sd-note' },
          'How often each method puts two cases in the order they ended (its concordance), comparing cases at the same '
          + 'point after filing. 50% is a coin toss.'),
        h('p', { class: 'sd-legend' },
          h('span', { class: 'sd-key sd-key-model' }), h('span', { class: 'sd-legend-name' }, 'This model'),
          h('span', { class: 'sd-key sd-key-diagonal' }), 'Simpler methods'),
        rankBox)),
    calTable,
    rankingTable(lines));
  host.append(el);
  const calTip = createTooltip(calBox);
  const rankTip = createTooltip(rankBox);
  const ruler = document.createElement('canvas').getContext('2d');
  let calHover = null;
  let rankHover = null;

  function render({ horizon }) {
    const points = calibration(data, MODEL, horizon);
    const mean = gap(data, MODEL, horizon);
    calTitle.textContent = `Calibration within ${describe.months(horizon)}`;
    calNote.textContent = 'Whether cases end as often as forecast. The forecasts of being legally final within '
      + `${describe.months(horizon)}, in bands of 10 points, against the share of those cases that were. On the diagonal `
      + `the two agree, and a larger dot stands for more forecasts. On average the bands are ${describe.points(mean)} from it.`;
    calibrationTable(points, horizon);
    calHover = drawCalibration(points, horizon);
    rankHover = drawRanking();
    calTip.hide();
    rankTip.hide();
    return describe.performanceLine({ forecasts, cases, horizon, gap: mean, ranking: model.values });
  }

  /** The hidden table of the calibration bands. */
  function calibrationTable(points, horizon) {
    calTable.replaceChildren(
      h('caption', {}, `Calibration within ${describe.months(horizon)}`),
      h('thead', {}, h('tr', {}, ...['Forecasts', 'Mean forecast', `Share legally final within ${describe.months(horizon)}`, 'Share of the forecasts']
        .map((name) => h('th', { scope: 'col' }, name)))),
      h('tbody', {}, ...points.map((point) => h('tr', {},
        h('th', { scope: 'row' }, band(point.bin)),
        h('td', {}, describe.share(point.forecast)),
        h('td', {}, describe.share(point.observed)),
        h('td', {}, describe.share(point.share))))));
  }

  /** The calibration chart, in a square that fits its box. Returns what hovering it needs. */
  function drawCalibration(points, horizon) {
    const width = calBox.clientWidth;
    const height = calBox.clientHeight;
    size(calSvg, width, height);
    if (width < 120 || height < 120) {
      calSvg.replaceChildren();
      return null;
    }
    const margin = { top: 8, right: 12, bottom: 36, left: 58 };
    const side = Math.min(width - margin.left - margin.right, height - margin.top - margin.bottom);
    const x0 = margin.left;
    const y0 = margin.top + side;
    const x = (p) => x0 + p * side;
    const y = (p) => y0 - p * side;

    const nodes = [];
    const labelled = side >= 160 ? [0, 0.25, 0.5, 0.75, 1] : [0, 0.5, 1];
    for (const p of [0, 0.25, 0.5, 0.75, 1]) {
      const kind = p === 0 ? 'sd-axis-line' : 'sd-grid';
      nodes.push(
        s('line', { class: kind, x1: x(0), x2: x(1), y1: y(p), y2: y(p) }),
        s('line', { class: kind, x1: x(p), x2: x(p), y1: y(0), y2: y(1) }),
      );
      if (!labelled.includes(p)) continue;
      nodes.push(
        s('text', { class: 'sd-tick', x: x0 - 8, y: y(p), dy: '0.32em', 'text-anchor': 'end' }, `${p * 100}%`),
        s('text', { class: 'sd-tick', x: x(p), y: y0 + 16, 'text-anchor': 'middle' }, `${p * 100}%`),
      );
    }
    nodes.push(
      s('text', { class: 'sd-tick', x: x(1), y: y0 + 30, 'text-anchor': 'end' }, 'Forecast probability'),
      s('text', { class: 'sd-tick', transform: `translate(12 ${y(1)}) rotate(-90)`, 'text-anchor': 'end' }, 'Share legally final'),
      s('line', { class: 'sd-diagonal', x1: x(0), y1: y(0), x2: x(1), y2: y(1) }),
    );
    const most = Math.max(...points.map((point) => point.share));
    const dots = points.map((point) => ({ ...point, cx: x(point.forecast), cy: y(point.observed), r: 3 + 6 * Math.sqrt(point.share / most) }));
    if (dots.length) nodes.push(s('path', { class: 'sd-forecast-line', d: polyline(dots.map((dot) => [dot.cx, dot.cy])) }));
    for (const dot of dots) nodes.push(s('circle', { class: 'sd-forecast-dot', cx: dot.cx, cy: dot.cy, r: dot.r }));
    calSvg.replaceChildren(...nodes);
    return { dots, horizon };
  }

  /** The ranking chart: a line per method across the landmarks, named at its end. */
  function drawRanking() {
    const width = rankBox.clientWidth;
    const height = rankBox.clientHeight;
    size(rankSvg, width, height);
    if (width < 160 || height < 100) {
      rankSvg.replaceChildren();
      return null;
    }
    ruler.font = `600 12px ${getComputedStyle(rankSvg).fontFamily}`;
    const names = Math.max(...lines.map((line) => ruler.measureText(line.name).width));
    const margin = { top: 8, right: names + 16, bottom: 36, left: 40 };
    const x = (i) => margin.left + (i / (LANDMARKS.length - 1)) * (width - margin.left - margin.right);
    const y = (v) => height - margin.bottom - ((v - RANGE[0]) / (RANGE[1] - RANGE[0])) * (height - margin.top - margin.bottom);

    const nodes = [];
    for (let percent = RANGE[0] * 100; percent <= RANGE[1] * 100; percent += 10) {
      const v = percent / 100;
      nodes.push(
        s('line', { class: v === RANGE[0] ? 'sd-axis-line' : 'sd-grid', x1: x(0), x2: x(LANDMARKS.length - 1), y1: y(v), y2: y(v) }),
        s('text', { class: 'sd-tick', x: margin.left - 8, y: y(v), dy: '0.32em', 'text-anchor': 'end' }, `${percent}%`),
      );
    }
    LANDMARKS.forEach((months, i) => {
      nodes.push(s('text', { class: 'sd-tick', x: x(i), y: height - margin.bottom + 16, 'text-anchor': 'middle' }, months ? String(months) : 'Filing'));
    });
    nodes.push(s('text', { class: 'sd-tick', x: x(LANDMARKS.length - 1), y: height - 4, 'text-anchor': 'end' }, 'Forecast made, months after filing'));

    // The simpler methods first, so the model's line is on top.
    const order = [...lines].sort((a, b) => (a.key === MODEL) - (b.key === MODEL));
    for (const line of order) {
      const isModel = line.key === MODEL;
      nodes.push(s('path', { class: isModel ? 'sd-forecast-line' : 'sd-curve-all', d: polyline(line.values.map((v, i) => [x(i), y(v)])) }));
      line.values.forEach((v, i) => nodes.push(s('circle', { class: isModel ? 'sd-forecast-dot' : 'sd-curve-dot', cx: x(i), cy: y(v), r: isModel ? DOT : DOT - 1 })));
    }
    const ends = spread(lines.map((line) => y(line.values.at(-1))), LINE);
    lines.forEach((line, i) => {
      nodes.push(s('text', {
        class: line.key === MODEL ? 'sd-end-name is-model' : 'sd-end-name',
        x: x(LANDMARKS.length - 1) + 10,
        y: ends[i],
        dy: '0.32em',
      }, line.name));
    });
    const cross = s('g', { class: 'sd-cross' });
    nodes.push(cross);
    rankSvg.replaceChildren(...nodes);
    return { x, y, cross, top: margin.top, bottom: height - margin.bottom };
  }

  // Hovering the calibration: the nearest dot's band, its mean forecast and what happened.
  calSvg.addEventListener('pointermove', (event) => {
    if (!calHover) return;
    const box = calSvg.getBoundingClientRect();
    const px = event.clientX - box.left;
    const py = event.clientY - box.top;
    let found = null;
    let distance = REACH;
    for (const dot of calHover.dots) {
      const d = Math.hypot(dot.cx - px, dot.cy - py) - dot.r;
      if (d < distance) {
        found = dot;
        distance = d;
      }
    }
    if (!found) {
      calTip.hide();
      return;
    }
    calTip.show([
      `Forecasts of ${band(found.bin)}`,
      `${describe.percent(found.forecast)} on average`,
      `${describe.percent(found.observed)} were legally final within ${describe.months(calHover.horizon)}`,
      `${describe.percent(found.share)} of the forecasts`,
    ], { x: found.cx, y: found.cy - found.r });
  });
  calSvg.addEventListener('pointerleave', () => calTip.hide());

  // Hovering the ranking: the nearest landmark, with every method's value there.
  rankSvg.addEventListener('pointermove', (event) => {
    if (!rankHover) return;
    const box = rankSvg.getBoundingClientRect();
    const px = event.clientX - box.left;
    const { x, y, cross, top, bottom } = rankHover;
    const i = Math.round(((px - x(0)) / (x(LANDMARKS.length - 1) - x(0))) * (LANDMARKS.length - 1));
    if (i < 0 || i >= LANDMARKS.length) {
      clearRanking();
      return;
    }
    cross.replaceChildren(
      s('line', { class: 'sd-cross-line', x1: x(i), x2: x(i), y1: top, y2: bottom }),
      ...lines.map((line) => s('circle', { class: line.key === MODEL ? 'sd-forecast-dot' : 'sd-curve-dot', cx: x(i), cy: y(line.values[i]), r: DOT + 1 })),
    );
    const sorted = [...lines].sort((a, b) => b.values[i] - a.values[i]);
    rankTip.show([
      LANDMARKS[i] ? `Forecasts made ${describe.months(LANDMARKS[i])} after filing` : 'Forecasts made at filing',
      ...sorted.map((line) => `${line.name}: ${describe.share(line.values[i])}`),
    ], { x: x(i), y: y(Math.max(...lines.map((line) => line.values[i]))) - DOT });
  });
  rankSvg.addEventListener('pointerleave', clearRanking);

  function clearRanking() {
    rankHover?.cross.replaceChildren();
    rankTip.hide();
  }

  return {
    render,
    destroy() {
      calTip.destroy();
      rankTip.destroy();
      el.remove();
    },
  };
}

/** The hidden table of each method's concordance at each landmark. */
function rankingTable(lines) {
  return h('table', { class: 'sd-sr-only' },
    h('caption', {}, 'How often each method puts two cases in the order they ended, by when the forecast was made'),
    h('thead', {}, h('tr', {},
      h('th', { scope: 'col' }, 'Method'),
      ...LANDMARKS.map((months) => h('th', { scope: 'col' }, months ? `${describe.months(months)} after filing` : 'At filing')))),
    h('tbody', {}, ...lines.map((line) => h('tr', {},
      h('th', { scope: 'row' }, line.name),
      ...line.values.map((v) => h('td', {}, describe.share(v)))))));
}

/** A calibration band: "70–80%". */
const band = (bin) => `${(bin * 100) / BINS}–${((bin + 1) * 100) / BINS}%`;

/** An SVG path through the points. */
const polyline = (points) => points.map(([px, py], i) => `${i ? 'L' : 'M'}${px.toFixed(1)},${py.toFixed(1)}`).join('');

/** Sizes an SVG to its box, in px. */
function size(svg, width, height) {
  svg.setAttribute('width', width);
  svg.setAttribute('height', height);
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
}
