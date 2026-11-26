// How well it does, on the Forecast tab: the scores of the model and the simpler methods side by side,
// on the test years, for all courts or the one selected, and the calibration of the method picked in
// the table.
//
// - The table gives each method's ranking (concordance) and its error (the Brier score) within 1, 3, 6
//   and 12 months, the best in each column in bold. A row is a radio button: it picks the method whose
//   calibration is drawn.
// - The calibration chart is over all courts and forecasts, since that's how it was computed: for each
//   band of 10 points, the mean forecast against the share of cases that ended in time, each dot sized
//   by its share of the forecasts, with the diagonal where the two agree.
//
// Colours come from CSS classes (see demo.css), so a theme change needs no redraw.

import { h, s } from '../dom.js';
import * as describe from '../format.js';
import { MODEL, MODELS, best, calibration, scoreTable } from '../scores.js';
import { createTooltip } from '../tooltip.js';

const REACH = 16; // px from a dot within which the pointer finds it
const BINS = 10;

let lastId = 0;

export function createScores(host, data) {
  const id = `sd-model-${++lastId}`;
  let selected = MODEL;
  let state = null;

  const meta = h('p', { class: 'sd-case-meta' });
  const cells = new Map(); // model key -> { row, input, concordance, brier: { h: td } }
  const body = h('tbody');
  const table = h('table', { class: 'sd-table' },
    h('caption', { class: 'sd-sr-only' }, 'The methods\' scores. Pick one to see its calibration.'),
    h('thead', {},
      h('tr', {},
        h('th', { scope: 'col', rowspan: 2 }, 'Method'),
        h('th', { scope: 'col', rowspan: 2, class: 'sd-num' }, 'Ranking'),
        h('th', { scope: 'colgroup', colspan: data.horizons.length, class: 'sd-num sd-group' }, 'Error within')),
      h('tr', {}, ...data.horizons.map((months) => h('th', { scope: 'col', class: 'sd-num' }, `${months} mo`)))),
    body);
  for (const model of MODELS) {
    const input = h('input', { type: 'radio', name: id, value: model.key, checked: model.key === selected });
    const row = h('tr', { class: model.key === MODEL ? 'is-model' : null },
      h('th', { scope: 'row' }, h('label', {}, input, h('span', {}, model.name))));
    const entry = { row, input, concordance: h('td', { class: 'sd-num' }), brier: {} };
    row.append(entry.concordance);
    for (const months of data.horizons) {
      entry.brier[months] = h('td', { class: 'sd-num' });
      row.append(entry.brier[months]);
    }
    input.addEventListener('change', () => pickModel(model.key));
    // The whole row picks the method, not just its name.
    row.addEventListener('click', (event) => {
      if (event.target !== input && !event.target.closest('label')) input.click();
    });
    cells.set(model.key, entry);
    body.append(row);
  }
  const about = h('p', { class: 'sd-about' });
  const note = h('p', { class: 'sd-note' },
    'Ranking: how often a method puts two cases in the order they ended (concordance; 0.5 is a coin toss). Error: the '
    + 'mean squared gap between the chance forecast and what happened (the Brier score). The best in each column is in '
    + 'bold. Every method was built on the cases registered in 2020–2023.');

  const calTitle = h('p', { class: 'sd-cal-title' });
  const svg = s('svg', { class: 'sd-chart', 'aria-hidden': 'true' });
  const calBox = h('div', { class: 'sd-chart-box' }, svg);
  const calNote = h('p', { class: 'sd-note' });
  const calLegend = h('p', { class: 'sd-legend' },
    h('span', { class: 'sd-key sd-key-model' }), h('span', { class: 'sd-legend-name' }), ' ',
    h('span', { class: 'sd-key sd-key-diagonal' }), 'Forecast and outcome agree');

  const el = h('div', { class: 'sd-scores' },
    h('div', { class: 'sd-case' }, h('p', { class: 'sd-case-title' }, 'How well it does'), meta),
    h('div', { class: 'sd-scores-body' },
      h('div', { class: 'sd-scores-table' }, table, about, note),
      h('div', { class: 'sd-calibration' }, calTitle, calNote, calLegend, calBox)));
  host.append(el);
  const tip = createTooltip(calBox);
  let hover = null;

  function pickModel(key) {
    selected = key;
    if (state) render(state);
  }

  function render(next) {
    state = next;
    const { court, landmark, horizon } = state;
    const when = court ? 'all' : landmark;
    const scores = scoreTable(data, court, when);
    const made = when === 'all' ? 'made at filing and 1, 3, 6 and 12 months after' : describe.landmark(when);
    meta.textContent = `${court ? court.name : 'All courts'}: ${describe.count(scores.forecasts)} forecasts, ${made}, `
      + `on ${court ? 'its' : 'the'} cases registered in 2024–2025.`;

    const ranking = best(scores.rows, (row) => row.concordance);
    const errors = Object.fromEntries(data.horizons.map((months) => [months, best(scores.rows, (row) => row.brier[months], { lower: true })]));
    for (const row of scores.rows) {
      const entry = cells.get(row.key);
      entry.row.classList.toggle('is-selected', row.key === selected);
      entry.input.checked = row.key === selected;
      entry.concordance.textContent = describe.score(row.concordance);
      entry.concordance.classList.toggle('is-best', ranking.includes(row));
      for (const months of data.horizons) {
        entry.brier[months].textContent = describe.score(row.brier[months]);
        entry.brier[months].classList.toggle('is-best', errors[months].includes(row));
      }
    }
    const chosen = scores.rows.find((row) => row.key === selected);
    about.textContent = `${chosen.name}: ${chosen.about}`;

    // Calibration is over all courts and forecasts.
    const overall = scoreTable(data, null).rows.find((row) => row.key === selected);
    calTitle.textContent = `Calibration within ${describe.months(horizon)}`;
    calLegend.querySelector('.sd-legend-name').textContent = chosen.name;
    calNote.textContent = 'Forecasts in bands of 10 points, against the share of those cases that ended in time, each dot '
      + `sized by its share of the forecasts. All courts. Mean gap: ${(overall.calibration[horizon] * 100).toFixed(1)} points.`;
    draw(calibration(data, selected, horizon), horizon);
    tip.hide();
    return describe.scoresLine(court, when, scores.forecasts, ranking, errors[horizon], horizon);
  }

  function draw(points, horizon) {
    const width = calBox.clientWidth;
    const height = calBox.clientHeight;
    svg.setAttribute('width', width);
    svg.setAttribute('height', height);
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    hover = null;
    if (width < 80 || height < 80) {
      svg.replaceChildren();
      return;
    }
    const margin = { top: 8, right: 10, bottom: 34, left: 58 };
    const side = Math.max(40, Math.min(width - margin.left - margin.right, height - margin.top - margin.bottom));
    const x0 = margin.left;
    const y0 = margin.top + side;
    const x = (p) => x0 + p * side;
    const y = (p) => y0 - p * side;

    const nodes = [];
    for (const p of [0, 0.5, 1]) {
      nodes.push(
        s('line', { class: p === 0 ? 'sd-axis-line' : 'sd-grid', x1: x(0), x2: x(1), y1: y(p), y2: y(p) }),
        s('line', { class: p === 0 ? 'sd-axis-line' : 'sd-grid', x1: x(p), x2: x(p), y1: y(0), y2: y(1) }),
        s('text', { class: 'sd-tick', x: x0 - 8, y: y(p), dy: '0.32em', 'text-anchor': 'end' }, `${p * 100}%`),
        s('text', { class: 'sd-tick', x: x(p), y: y0 + 16, 'text-anchor': 'middle' }, `${p * 100}%`),
      );
    }
    nodes.push(
      s('text', { class: 'sd-tick', x: x(1), y: y0 + 30, 'text-anchor': 'end' }, 'Forecast chance of ending'),
      s('text', { class: 'sd-tick', transform: `translate(12 ${y(1)}) rotate(-90)`, 'text-anchor': 'end' }, 'Share that ended'),
      s('line', { class: 'sd-diagonal', x1: x(0), y1: y(0), x2: x(1), y2: y(1) }),
    );
    const most = Math.max(...points.map((point) => point.share));
    const dots = points.map((point) => ({ ...point, cx: x(point.forecast), cy: y(point.observed), r: 4 + 6 * Math.sqrt(point.share / most) }));
    if (dots.length) {
      nodes.push(s('path', { class: 'sd-forecast-line', d: dots.map((dot, i) => `${i ? 'L' : 'M'}${dot.cx.toFixed(1)},${dot.cy.toFixed(1)}`).join('') }));
    }
    for (const dot of dots) nodes.push(s('circle', { class: 'sd-forecast-dot', cx: dot.cx, cy: dot.cy, r: dot.r }));
    svg.replaceChildren(...nodes);
    hover = { dots, horizon };
  }

  function onMove(event) {
    if (!hover) return;
    const box = svg.getBoundingClientRect();
    const px = event.clientX - box.left;
    const py = event.clientY - box.top;
    let found = null;
    let distance = REACH;
    for (const dot of hover.dots) {
      const d = Math.hypot(dot.cx - px, dot.cy - py) - dot.r;
      if (d < distance) {
        found = dot;
        distance = d;
      }
    }
    if (!found) {
      tip.hide();
      return;
    }
    const band = `${found.bin * BINS}–${(found.bin + 1) * BINS}%`;
    tip.show([
      `${describe.percent(found.observed)} ended within ${describe.months(hover.horizon)}`,
      `Forecasts of ${band}, ${describe.percent(found.forecast)} on average`,
      `${describe.percent(found.share)} of the forecasts`,
    ], { x: found.cx, y: found.cy - found.r });
  }

  svg.addEventListener('pointermove', onMove);
  svg.addEventListener('pointerleave', () => tip.hide());

  return {
    render,
    destroy() {
      tip.destroy();
      el.remove();
    },
  };
}
