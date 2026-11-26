// The demo's entry point. Vite bundles it with the kit and the CSS into demo.js and demo.css.
//
// It loads the data, then mounts the frame with the controls, showing only those the current tab uses.
// The tabs (views/) draw the stage; this module keeps the state they share: the tab, the court
// selected (or none, for all courts), and the real past case on the Forecast tab, with the day of its
// forecast. The status line shows what's selected, with its headline numbers.

import manifest from 'virtual:manifest';
import { loadJSON, mount, slider } from '@mark-bugden/demo-kit';
import '@mark-bugden/demo-kit/tokens.scoped.css';
import '@mark-bugden/demo-kit/frame.css';
import './demo.css';
import { findCases, ordered, pick } from './cases.js';
import { button, search, segmented } from './controls.js';
import { matches, searchIndex } from './courts.js';
import { prepare } from './data.js';
import { h } from './dom.js';
import * as describe from './format.js';
import { createForecast } from './views/forecast.js';
import { createPlaceholder } from './views/placeholder.js';

// The tabs' icons, on a 24 × 24 grid: a curve falling over time, and stages in a row with a loop back.
const ICONS = {
  forecast: '<path d="M4 4v16h16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
    + '<path d="M6.5 6.5c3.5 0 4.5 3 6.5 6s3.5 4 6.5 4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  map: '<path d="M6.5 15h3M14.5 15h3M20 12c0-7-8-7-8 0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>'
    + '<g fill="currentColor"><circle cx="4" cy="15" r="2.5"/><circle cx="12" cy="15" r="2.5"/><circle cx="20" cy="15" r="2.5"/></g>',
  // A die showing five.
  random: '<rect x="4" y="4" width="16" height="16" rx="3" fill="none" stroke="currentColor" stroke-width="1.5"/>'
    + '<g fill="currentColor"><circle cx="8.5" cy="8.5" r="1.5"/><circle cx="15.5" cy="8.5" r="1.5"/><circle cx="12" cy="12" r="1.5"/>'
    + '<circle cx="8.5" cy="15.5" r="1.5"/><circle cx="15.5" cy="15.5" r="1.5"/></g>',
};
const TABS = {
  forecast: { label: 'Forecast', create: createForecast },
  map: { label: 'Process map', create: (host) => createPlaceholder(host, 'Process map') },
};
// The case the demo opens on: an ordinary one, with a hearing and a decision.
const OPENING = { court: 'OSJIMJI', label: '18 C 33/2024' };

async function start(el) {
  const data = prepare(await loadJSON('data/soudai.json'));
  const index = searchIndex(data.courts);
  // Every real case, by court in order of area, then by number.
  const allCases = ordered(data.cases, index.map((entry) => entry.court));
  const casesOf = (court) => (court ? ordered(court.cases, [court]) : allCases);
  let item = data.court(OPENING.court).cases.find((c) => c.label === OPENING.label) ?? data.cases[0];

  const tab = segmented({
    label: 'View',
    showLabel: false,
    options: Object.entries(TABS).map(([value, { label }]) => ({ label, value, icon: ICONS[value] })),
    value: 'forecast',
  });
  const court = search({
    label: 'Court',
    placeholder: 'All courts',
    // Opened empty, the list starts with all courts, so there's a way back to them besides clearing the box.
    suggest: (query) => [
      ...(query ? [] : [{ label: 'All courts', detail: describe.registered(data.journey(null)), value: null }]),
      ...matches(index, query).map((c) => ({ label: c.name, detail: describe.registered(c.journey), value: c })),
    ],
    format: (c) => c.name,
    empty: 'No court by that name',
    browse: true,
  });
  const realCase = search({
    label: 'Case',
    placeholder: 'Case number',
    // The selected court's cases, or every court's, each with its court or its filing date.
    suggest: (query) => findCases(casesOf(court.value), query).map((c) => ({
      label: c.label,
      detail: court.value ? `Filed ${describe.date(c.filed, true)}` : c.court.name,
      value: c,
    })),
    format: (c) => c.label,
    empty: 'No case by that number',
    browse: true,
  });
  const random = button({ label: 'Random case', icon: ICONS.random });
  const day = slider({
    label: 'Forecast on',
    min: 0,
    max: item.span - 1,
    step: 1,
    value: 0,
    format: (d) => (d === 0 ? `Filing, ${describe.date(item.filed, true)}` : `Day ${describe.count(d)}, ${describe.date(describe.addDays(item.filed, d), true)}`),
  });
  const controls = { tab, court, realCase, random, day };
  // The controls each tab uses, besides the tab switch.
  const USED = { forecast: [court, realCase, random, day], map: [court] };

  /** Shows a case, from its filing. */
  function choose(next) {
    item = next;
    realCase.value = item;
    day.el.querySelector('input').max = String(item.span - 1);
    day.value = 0;
  }
  choose(item);
  // A court that isn't the case's brings one of its own cases.
  court.onChange((c) => {
    if (c && item.court !== c) choose(pick(casesOf(c)));
  });
  // Clearing the case box leaves the case as it was.
  realCase.onChange((c) => (c ? choose(c) : (realCase.value = item)));
  random.onChange(() => choose(pick(casesOf(court.value), item)));

  let current = null; // { name, view }
  let host = null;

  const app = mount({
    el,
    manifest,
    controls,
    render({ stage, width, height, values }) {
      // A stage with no size, such as one hidden for a moment, has nothing to draw. The frame
      // redraws when it has a size again.
      if (width < 1 || height < 1) return;
      if (!host) {
        host = h('div', { class: 'sd-view' });
        stage.append(host);
      }
      if (current?.name !== values.tab) {
        current?.view.destroy();
        current = { name: values.tab, view: TABS[values.tab].create(host, data) };
        stage.setAttribute('aria-label', TABS[values.tab].label);
      }
      showControls();
      const status = current.view.render({ width, height, court: values.court, item, day: values.day });
      app.status(status ?? describe.headline(values.court, data.journey(values.court), data.courts.length));
    },
  });
  app.stage.setAttribute('role', 'region');
  el.querySelector('.dk-status')?.setAttribute('aria-live', 'polite');
  // Before the first draw, so the controls the opening tab doesn't use never show.
  showControls();

  /** Shows the controls the tab uses, and hides the rest. */
  function showControls() {
    const used = new Set([tab, ...USED[tab.value]]);
    for (const control of Object.values(controls)) control.el.hidden = !used.has(control);
  }
}

const el = document.querySelector(`[data-demo="${manifest.slug}"]`);
start(el).catch((error) => {
  // The still image stays in place.
  console.error('soudai: could not start the demo', error);
});
