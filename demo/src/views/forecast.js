// The Forecast tab, for a real past case or a custom one: the case, the chance it ends within 1, 3, 6
// and 12 months of the day chosen, and for a real case whether it did, over a chart of its life.
//
// The chart shares one time axis, in months after filing:
// - above, the case's events, one lane per stage it reached. Those up to the day of the forecast are
//   what the network reads; those after it, in the curve colour, are what happened next;
// - below, the forecast: the chance the case has ended, month by month for 12 months from the day of
//   the forecast, which is the line in the accent across both;
// - for a real case, the day it ended, or its record ran out, as a line in the contrasting highlight.
//
// A custom case has nothing after the forecast, so its axis runs to 12 months after the day of the
// forecast.
//
// Colours come from CSS classes (see demo.css), so a theme change needs no redraw.

import { ending, forecast, outcome, soFar } from '../cases.js';
import { h, s } from '../dom.js';
import { MONTH, within } from '../forecast.js';
import * as describe from '../format.js';
import { createTooltip } from '../tooltip.js';

const AHEAD = 12; // months of the forecast drawn
const OUTCOME = { yes: 'It did', no: 'It didn\'t', unknown: 'Not known' };
const OUTCOME_TITLE = {
  yes: 'It ended within this time.',
  no: 'It was still open after this time.',
  unknown: 'Its record ends before this time, with the case still open.',
};
const LANE = [13, 20]; // px per lane of events, at least and at most
const PANEL = 110; // px: the forecast's panel is at least this tall, if the lanes can shrink to fit
const DOT = 4.5; // px, an event's radius
const REACH = 14; // px from a dot within which the pointer finds it
const STAGE_ORDER = Object.keys(describe.STAGES);

export function createForecast(host, data) {
  const title = h('p', { class: 'sd-case-title' });
  const meta = h('p', { class: 'sd-case-meta' });
  const tiles = data.horizons.map(() => {
    const value = h('span', { class: 'sd-tile-value' });
    const result = h('span', { class: 'sd-tile-outcome' });
    const label = h('span', { class: 'sd-tile-label' });
    return { el: h('div', { class: 'sd-tile', role: 'listitem' }, label, value, result), label, value, result };
  });
  const svg = s('svg', { class: 'sd-chart', 'aria-hidden': 'true' });
  const chart = h('div', { class: 'sd-chart-box' }, svg);
  const events = h('ol', { class: 'sd-sr-only', 'aria-label': 'Events' });
  const el = h('div', { class: 'sd-forecast' },
    h('div', { class: 'sd-case' }, title, meta),
    h('div', { class: 'sd-chances' },
      h('p', { class: 'sd-chances-label', id: 'sd-chances-label' }, 'Chance it ends within'),
      h('div', { class: 'sd-tiles', role: 'list', 'aria-labelledby': 'sd-chances-label' }, ...tiles.map((tile) => tile.el))),
    chart,
    events);
  host.append(el);
  const tip = createTooltip(chart);

  let hover = null; // what the pointer can find: { dots, forecast }

  function render({ item, day }) {
    const so = soFar(item, day);
    const still = forecast(data, item.court, so, day);
    const chances = within(still, data.horizons);
    const end = item.made ? null : ending(item);

    title.textContent = item.label;
    meta.textContent = `${item.court.name} · filed ${describe.date(item.filed)}`;
    data.horizons.forEach((months, i) => {
      const tile = tiles[i];
      tile.label.textContent = describe.months(months);
      tile.value.textContent = describe.percent(chances[i]);
      tile.result.hidden = Boolean(item.made);
      if (item.made) return;
      const result = outcome(item, day, months);
      tile.result.textContent = OUTCOME[result];
      tile.result.dataset.outcome = result;
      tile.result.title = OUTCOME_TITLE[result];
    });
    events.replaceChildren(...item.events.map((event) => h('li', {},
      `${when(item, event.day)}: ${event.code.gloss}${event.day > day ? ' (after the forecast)' : ''}`)));

    draw(item, day, still, end);
    tip.hide();
    return item.made
      ? describe.customLine(item, day, chances, data.horizons)
      : describe.forecastLine(item, day, chances, data.horizons, end);
  }

  function draw(item, day, still, end) {
    const width = chart.clientWidth;
    const height = chart.clientHeight;
    svg.setAttribute('width', width);
    svg.setAttribute('height', height);
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    if (width < 40 || height < 80) {
      svg.replaceChildren();
      hover = null;
      return;
    }

    const lanes = STAGE_ORDER.filter((stage) => item.events.some((event) => event.code.lane === stage));
    const narrow = width < 420;
    const left = narrow ? 78 : 96;
    const right = 14;
    const top = 20;
    const axisHeight = 34;
    const lane = Math.min(LANE[1], Math.max(LANE[0], (height - top - 26 - axisHeight - PANEL) / lanes.length));
    const lanesBottom = top + lanes.length * lane;
    const panelTop = lanesBottom + 26;
    const panelBottom = Math.max(panelTop + 40, height - axisHeight);
    const last = (item.made ? day : item.span) + AHEAD * MONTH;
    const x = (d) => left + (d / last) * (width - left - right);
    const y = (p) => panelBottom - p * (panelBottom - panelTop);
    const laneY = (stage) => top + (lanes.indexOf(stage) + 0.5) * lane;

    const nodes = [];
    const labels = []; // drawn over the lines, with a halo in the surface colour

    // Lanes: a hairline each, with the stage's name on the left.
    for (const stage of lanes) {
      nodes.push(
        s('line', { class: 'sd-lane', x1: left, x2: width - right, y1: laneY(stage), y2: laneY(stage) }),
      );
      labels.push(s('text', { class: 'sd-label', x: left - 10, y: laneY(stage), dy: '0.32em', 'text-anchor': 'end' }, describe.STAGES[stage]));
    }

    // The forecast panel: gridlines at 0, 50% and 100%, and its title.
    for (const p of [0, 0.5, 1]) {
      nodes.push(
        s('line', { class: p === 0 ? 'sd-axis-line' : 'sd-grid', x1: left, x2: width - right, y1: y(p), y2: y(p) }),
        s('text', { class: 'sd-tick', x: left - 10, y: y(p), dy: '0.32em', 'text-anchor': 'end' }, `${p * 100}%`),
      );
    }
    labels.push(s('text', { class: 'sd-label', x: left + 6, y: panelTop - 10 }, 'Chance it has ended'));

    // The time axis: months after filing.
    const step = [1, 2, 3, 6, 12, 24].find((m) => x(m * MONTH) - x(0) >= 44) ?? 24;
    for (let m = 0; m * MONTH <= last; m += step) {
      nodes.push(s('text', { class: 'sd-tick', x: x(m * MONTH), y: panelBottom + 16, 'text-anchor': 'middle' }, String(m)));
    }
    nodes.push(s('text', { class: 'sd-tick', x: width - right, y: panelBottom + 30, 'text-anchor': 'end' }, 'Months after filing'));

    // The forecast: the chance it has ended k months after the day of the forecast, for k = 0 to 12.
    const points = [[day, 0]];
    for (let k = 1; k <= AHEAD; k++) points.push([day + k * MONTH, 1 - still[k - 1]]);
    const path = points.map(([d, p], i) => `${i ? 'L' : 'M'}${x(d).toFixed(1)},${y(p).toFixed(1)}`).join('');
    nodes.push(
      s('path', { class: 'sd-forecast-area', d: `${path}L${x(points.at(-1)[0]).toFixed(1)},${y(0)}Z` }),
      s('path', { class: 'sd-forecast-line', d: path }),
    );
    for (const months of data.horizons) {
      nodes.push(s('circle', { class: 'sd-forecast-dot', cx: x(day + months * MONTH), cy: y(1 - still[months - 1]), r: DOT }));
    }

    // The day a real case ended, or its record ran out, labelled where the forecast's line isn't.
    if (!item.made) {
      const endX = x(item.span);
      const reached = item.span <= day + AHEAD * MONTH ? curveAt(points, item.span) : 0;
      const endLabel = end === 'open' ? 'Record ends' : `Ended, day ${describe.count(item.span)}`;
      const labelY = reached > 0.5 ? panelBottom - 6 : panelTop + 12;
      const anchor = endX > width - right - 90 ? 'end' : 'start';
      nodes.push(s('line', { class: end === 'open' ? 'sd-record-end' : 'sd-ended', x1: endX, x2: endX, y1: panelTop - 4, y2: panelBottom }));
      labels.push(s('text', { class: 'sd-end-label', x: endX + (anchor === 'start' ? 6 : -6), y: labelY, 'text-anchor': anchor }, endLabel));
    }

    // The day of the forecast, across the lanes and the panel.
    const nowX = x(day);
    nodes.push(s('line', { class: 'sd-now', x1: nowX, x2: nowX, y1: top - 4, y2: panelBottom }));
    labels.push(s('text', { class: 'sd-now-label', x: Math.min(Math.max(nowX, left + 26), width - right - 26), y: top - 8, 'text-anchor': 'middle' }, 'Forecast'));

    // Events: one dot per lane and day, those after the forecast in the curve colour.
    const dots = [];
    const byDot = new Map();
    for (const event of item.events) {
      const key = `${event.code.lane}:${event.day}`;
      if (!byDot.has(key)) byDot.set(key, { lane: event.code.lane, day: event.day, events: [] });
      byDot.get(key).events.push(event);
    }
    for (const dot of byDot.values()) {
      if (!lanes.includes(dot.lane)) continue;
      dot.x = x(dot.day);
      dot.y = laneY(dot.lane);
      nodes.push(s('circle', { class: dot.day <= day ? 'sd-event' : 'sd-event is-next', cx: dot.x, cy: dot.y, r: DOT }));
      dots.push(dot);
    }

    const cross = s('g', { class: 'sd-cross' });
    nodes.push(...labels, cross);
    svg.replaceChildren(...nodes);
    hover = { item, day, still, dots, x, y, panelTop, panelBottom, cross };
  }

  // Hover: an event's dot gives its events; the forecast panel gives the chance at the nearest month.
  function onMove(event) {
    if (!hover) return;
    const box = svg.getBoundingClientRect();
    const px = event.clientX - box.left;
    const py = event.clientY - box.top;
    const { item, day, still, dots, x, y, panelTop, panelBottom, cross } = hover;
    cross.replaceChildren();

    let best = null;
    let bestDistance = REACH;
    for (const dot of dots) {
      const distance = Math.hypot(dot.x - px, dot.y - py);
      if (distance < bestDistance) {
        best = dot;
        bestDistance = distance;
      }
    }
    if (best) {
      const lines = [when(item, best.day), ...best.events.map((e) => e.code.gloss)];
      if (best.day > day) lines.push('After the forecast');
      tip.show(lines, { x: best.x, y: best.y - DOT });
      return;
    }

    if (py >= panelTop - 8 && py <= panelBottom + 8) {
      const months = Math.round(((px - x(day)) / (x(day + MONTH) - x(day))));
      if (months >= 1 && months <= AHEAD) {
        const at = day + months * MONTH;
        const p = 1 - still[months - 1];
        cross.append(
          s('line', { class: 'sd-cross-line', x1: x(at), x2: x(at), y1: panelTop, y2: panelBottom }),
          s('circle', { class: 'sd-forecast-dot', cx: x(at), cy: y(p), r: DOT }),
        );
        const by = describe.date(describe.addDays(item.filed, Math.round(at)));
        tip.show([`${describe.percent(p)} within ${describe.months(months)}`, `By ${by}`], { x: x(at), y: y(p) - DOT });
        return;
      }
    }
    tip.hide();
  }

  function onLeave() {
    hover?.cross.replaceChildren();
    tip.hide();
  }

  svg.addEventListener('pointermove', onMove);
  svg.addEventListener('pointerleave', onLeave);

  return {
    render,
    destroy() {
      tip.destroy();
      el.remove();
    },
  };
}

/** "21 March 2024, day 177". */
function when(item, day) {
  return `${describe.date(describe.addDays(item.filed, day))}, day ${describe.count(day)}`;
}

/** The forecast's chance of having ended by day `d`, read off its line between the months. */
function curveAt(points, d) {
  for (let i = 1; i < points.length; i++) {
    const [d0, p0] = points[i - 1];
    const [d1, p1] = points[i];
    if (d <= d1) return p0 + ((d - d0) / (d1 - d0)) * (p1 - p0);
  }
  return points.at(-1)[1];
}
