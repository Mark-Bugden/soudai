// The Performance tab: how well the model does on the cases registered in 2024–2025, which it never
// trained on, over all courts.
//
// - Calibration: for each band of 10 points, the model's mean forecast that a case is legally final
//   within the months chosen in the rail, against the share of those cases that were, each dot sized by
//   its share of the forecasts, with the diagonal where the two agree.
// - Ranking: how often the model and three simpler methods put two cases in the order they ended
//   (concordance), for forecasts made at filing and 1, 3, 6 and 12 months after, each line named at its
//   end. The model is in the accent and the others in the curve colour; the rail says what each is.
//
// Hovering either chart reads the model's value off its y axis, as on the Process map's curve, with no
// tooltips: everything else can be read off the axes or the notes. Hidden tables give both charts to screen readers. Colours come from CSS
// classes (see demo.css), so a theme change needs no redraw.

import { h, s } from '../dom.js';
import * as describe from '../format.js';
import { BINS, LANDMARKS, METHODS, MODEL, calibration, counts, gap, ranking } from '../performance.js';
import { clearReading, showReading, stack } from '../reading.js';

const LINE = 15; // px between the names at the ends of the ranking's lines
const RANGE = [0.5, 0.8]; // the ranking's axis, from a coin toss
const DOT = 4; // px, a landmark's dot on the ranking

// A method's line and dots: the model's, or a simpler method's.
const MARKS = {
  model: { line: 'sd-forecast-line', dot: 'sd-forecast-dot' },
  other: { line: 'sd-curve-all', dot: 'sd-curve-dot' },
};
const marks = (key) => MARKS[key === MODEL ? 'model' : 'other'];
const method = (key) => METHODS.find((m) => m.key === key);

export function createPerformance(host, data) {
  const { forecasts, cases } = counts(data);

  const legend = h('p', { class: 'sd-legend' },
    h('span', { class: 'sd-key sd-key-model' }), h('span', { class: 'sd-legend-name' }, 'This model'),
    h('span', { class: 'sd-key sd-key-diagonal' }), 'Simpler methods');
  const calTitle = h('p', { class: 'sd-cal-title' });
  const calNote = h('p', { class: 'sd-note' });
  const calSvg = s('svg', { class: 'sd-chart', 'aria-hidden': 'true' });
  const calBox = h('div', { class: 'sd-chart-box sd-perf-box' }, calSvg);
  const rankSvg = s('svg', { class: 'sd-chart', 'aria-hidden': 'true' });
  const rankBox = h('div', { class: 'sd-chart-box sd-perf-box' }, rankSvg);
  const calTable = h('table', { class: 'sd-sr-only' });
  const rankTable = h('table', { class: 'sd-sr-only' });
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
        legend,
        rankBox)),
    calTable,
    rankTable);
  host.append(el);
  const ruler = document.createElement('canvas').getContext('2d');
  let calRead = null; // what reading each chart needs
  let rankRead = null;

  function render({ horizon }) {
    // The calibration is the model's alone (Mark: comparing it there didn't help).
    const series = [{ ...method(MODEL), points: calibration(data, MODEL, horizon), gap: gap(data, MODEL, horizon) }];
    const lines = ranking(data);
    calTitle.textContent = `Calibration within ${describe.months(horizon)}`;
    calNote.textContent = 'Whether cases end as often as forecast. The forecasts of being legally final within '
      + `${describe.months(horizon)}, in bands of 10 points, against the share of those cases that were. On the diagonal `
      + `the two agree, and a larger dot stands for more forecasts. On average the bands are ${describe.points(series[0].gap)} from it.`;

    describeCalibration(series, horizon);
    describeRanking(lines);
    calRead = drawCalibration(series);
    rankRead = drawRanking(lines);
    return describe.performanceLine({ forecasts, cases, horizon, gap: series[0].gap, lines });
  }

  /** The hidden table of the calibration bands, a row per method and band. */
  function describeCalibration(series, horizon) {
    calTable.replaceChildren(
      h('caption', {}, `Calibration within ${describe.months(horizon)}`),
      h('thead', {}, h('tr', {}, ...['Method', 'Forecasts', 'Mean forecast', `Share legally final within ${describe.months(horizon)}`, 'Share of the forecasts']
        .map((name) => h('th', { scope: 'col' }, name)))),
      h('tbody', {}, ...series.flatMap(({ name, points }) => points.map((point) => h('tr', {},
        h('th', { scope: 'row' }, name),
        h('td', {}, band(point.bin)),
        h('td', {}, describe.share(point.forecast)),
        h('td', {}, describe.share(point.observed)),
        h('td', {}, describe.share(point.share)))))));
  }

  /** The hidden table of each method's concordance at each landmark. */
  function describeRanking(lines) {
    rankTable.replaceChildren(
      h('caption', {}, 'How often each method puts two cases in the order they ended, by when the forecast was made'),
      h('thead', {}, h('tr', {},
        h('th', { scope: 'col' }, 'Method'),
        ...LANDMARKS.map((months) => h('th', { scope: 'col' }, months ? `${describe.months(months)} after filing` : 'At filing')))),
      h('tbody', {}, ...lines.map((line) => h('tr', {},
        h('th', { scope: 'row' }, line.name),
        ...line.values.map((v) => h('td', {}, describe.share(v)))))));
  }

  /** The calibration chart, in a square that fits its box, with a line of dots per series. */
  function drawCalibration(series) {
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
    const ticks = [];
    const labelled = side >= 160 ? [0, 0.25, 0.5, 0.75, 1] : [0, 0.5, 1];
    for (const p of [0, 0.25, 0.5, 0.75, 1]) {
      const kind = p === 0 ? 'sd-axis-line' : 'sd-grid';
      nodes.push(
        s('line', { class: kind, x1: x(0), x2: x(1), y1: y(p), y2: y(p) }),
        s('line', { class: kind, x1: x(p), x2: x(p), y1: y(0), y2: y(1) }),
      );
      if (!labelled.includes(p)) continue;
      const tick = s('text', { class: 'sd-tick', x: x0 - 8, y: y(p), dy: '0.32em', 'text-anchor': 'end' }, `${p * 100}%`);
      ticks.push({ tick, at: y(p) });
      nodes.push(tick, s('text', { class: 'sd-tick', x: x(p), y: y0 + 16, 'text-anchor': 'middle' }, `${p * 100}%`));
    }
    nodes.push(
      s('text', { class: 'sd-tick', x: x(1), y: y0 + 30, 'text-anchor': 'end' }, 'Forecast probability'),
      s('text', { class: 'sd-tick', transform: `translate(12 ${y(1)}) rotate(-90)`, 'text-anchor': 'end' }, 'Share legally final'),
      s('line', { class: 'sd-diagonal', x1: x(0), y1: y(0), x2: x(1), y2: y(1) }),
    );
    // Dots are sized by their share of the forecasts, on one scale for both methods.
    const most = Math.max(...series.flatMap(({ points }) => points.map((point) => point.share)));
    const dotted = series.map(({ key, points }) => ({
      key,
      dots: points.map((point) => ({ ...point, cx: x(point.forecast), cy: y(point.observed), r: 3 + 6 * Math.sqrt(point.share / most) })),
    }));
    for (const { key, dots } of dotted) {
      if (dots.length) nodes.push(s('path', { class: marks(key).line, d: polyline(dots.map((dot) => [dot.cx, dot.cy])) }));
      for (const dot of dots) nodes.push(s('circle', { class: marks(key).dot, cx: dot.cx, cy: dot.cy, r: dot.r }));
    }
    const reading = s('g', { class: 'sd-reading' });
    nodes.push(reading);
    calSvg.replaceChildren(...nodes);
    return { dotted, reading, ticks, x0, y, right: x(1) };
  }

  /** The ranking chart: a line per method across the landmarks, named at its end. */
  function drawRanking(lines) {
    const width = rankBox.clientWidth;
    const height = rankBox.clientHeight;
    size(rankSvg, width, height);
    if (width < 160 || height < 100) {
      rankSvg.replaceChildren();
      return null;
    }
    ruler.font = `600 12px ${getComputedStyle(rankSvg).fontFamily}`;
    const names = Math.max(...lines.map((line) => ruler.measureText(line.name).width));
    const margin = { top: 8, right: names + 16, bottom: 36, left: 52 };
    const x = (i) => margin.left + (i / (LANDMARKS.length - 1)) * (width - margin.left - margin.right);
    const y = (v) => height - margin.bottom - ((v - RANGE[0]) / (RANGE[1] - RANGE[0])) * (height - margin.top - margin.bottom);

    const nodes = [];
    const ticks = [];
    for (let percent = RANGE[0] * 100; percent <= RANGE[1] * 100; percent += 10) {
      const v = percent / 100;
      const tick = s('text', { class: 'sd-tick', x: margin.left - 8, y: y(v), dy: '0.32em', 'text-anchor': 'end' }, `${percent}%`);
      ticks.push({ tick, at: y(v) });
      nodes.push(s('line', { class: v === RANGE[0] ? 'sd-axis-line' : 'sd-grid', x1: x(0), x2: x(LANDMARKS.length - 1), y1: y(v), y2: y(v) }), tick);
    }
    LANDMARKS.forEach((months, i) => {
      nodes.push(s('text', { class: 'sd-tick', x: x(i), y: height - margin.bottom + 16, 'text-anchor': 'middle' }, months ? String(months) : 'Filing'));
    });
    nodes.push(s('text', { class: 'sd-tick', x: x(LANDMARKS.length - 1), y: height - 4, 'text-anchor': 'end' }, 'Forecast made, months after filing'));

    // The simpler methods first, so the model's line is on top.
    for (const line of lines) {
      const { line: path, dot } = marks(line.key);
      nodes.push(s('path', { class: path, d: polyline(line.values.map((v, i) => [x(i), y(v)])) }));
      line.values.forEach((v, i) => nodes.push(s('circle', { class: dot, cx: x(i), cy: y(v), r: DOT })));
    }
    const ends = stack(lines.map((line) => y(line.values.at(-1))), LINE);
    lines.forEach((line, i) => {
      nodes.push(s('text', {
        class: line.key === MODEL ? 'sd-end-name is-lit' : 'sd-end-name',
        x: x(LANDMARKS.length - 1) + 10,
        y: ends[i],
        dy: '0.32em',
      }, line.name));
    });
    const reading = s('g', { class: 'sd-reading' });
    nodes.push(reading);
    rankSvg.replaceChildren(...nodes);
    return { lines, x, y, reading, ticks, left: margin.left };
  }

  // Reading the calibration off its y axis, at the model's band nearest the pointer.
  calSvg.addEventListener('pointermove', (event) => {
    if (!calRead) return;
    const px = event.clientX - calSvg.getBoundingClientRect().left;
    const { dotted, reading, ticks, x0, y, right } = calRead;
    const model = dotted.at(-1).dots;
    if (px < x0 - 8 || px > right + 8 || !model.length) {
      clearReading(reading, ticks);
      return;
    }
    const near = model.reduce((best, dot) => (Math.abs(dot.cx - px) < Math.abs(best.cx - px) ? dot : best));
    const values = dotted.map(({ key, dots }) => [key, dots.find((dot) => dot.bin === near.bin)])
      .filter(([, dot]) => dot)
      .map(([key, dot]) => ({ cx: dot.cx, at: dot.cy, r: dot.r, text: describe.percent(dot.observed), dot: marks(key).dot }));
    showReading(reading, { x: near.cx, top: y(1), bottom: y(0), left: x0, values, ticks });
  });
  calSvg.addEventListener('pointerleave', () => calRead && clearReading(calRead.reading, calRead.ticks));

  // Reading the model's ranking off the y axis, at the nearest landmark.
  rankSvg.addEventListener('pointermove', (event) => {
    if (!rankRead) return;
    const px = event.clientX - rankSvg.getBoundingClientRect().left;
    const { lines, x, y, reading, ticks, left } = rankRead;
    const i = Math.round(((px - x(0)) / (x(LANDMARKS.length - 1) - x(0))) * (LANDMARKS.length - 1));
    if (i < 0 || i >= LANDMARKS.length) {
      clearReading(reading, ticks);
      return;
    }
    showReading(reading, {
      x: x(i),
      top: y(RANGE[1]),
      bottom: y(RANGE[0]),
      left,
      values: lines.filter((line) => line.key === MODEL)
        .map((line) => ({ cx: x(i), at: y(line.values[i]), text: describe.share(line.values[i]), dot: marks(line.key).dot })),
      ticks,
    });
  });
  rankSvg.addEventListener('pointerleave', () => rankRead && clearReading(rankRead.reading, rankRead.ticks));

  return {
    render,
    destroy() {
      el.remove();
    },
  };
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
