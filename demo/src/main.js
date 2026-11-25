// The demo's entry point. Vite bundles it with the kit and the CSS into demo.js and demo.css.
//
// It loads the data, then mounts the frame with the controls, showing only those the current tab uses.
// The tabs (views/) draw the stage; this module keeps the state they share: the tab, and the court
// selected, or none for all courts. The status line shows what's selected, with its headline numbers.

import manifest from 'virtual:manifest';
import { loadJSON, mount } from '@mark-bugden/demo-kit';
import '@mark-bugden/demo-kit/tokens.scoped.css';
import '@mark-bugden/demo-kit/frame.css';
import './demo.css';
import { search, segmented } from './controls.js';
import { matches, searchIndex } from './courts.js';
import { prepare } from './data.js';
import { h } from './dom.js';
import * as describe from './format.js';
import { createPlaceholder } from './views/placeholder.js';

// The tabs' icons, on a 24 × 24 grid: a curve falling over time, and stages in a row with a loop back.
const ICONS = {
  forecast: '<path d="M4 4v16h16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
    + '<path d="M6.5 6.5c3.5 0 4.5 3 6.5 6s3.5 4 6.5 4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  map: '<path d="M6.5 15h3M14.5 15h3M20 12c0-7-8-7-8 0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>'
    + '<g fill="currentColor"><circle cx="4" cy="15" r="2.5"/><circle cx="12" cy="15" r="2.5"/><circle cx="20" cy="15" r="2.5"/></g>',
};
const TABS = {
  forecast: { label: 'Forecast', create: (host) => createPlaceholder(host, 'Forecast') },
  map: { label: 'Process map', create: (host) => createPlaceholder(host, 'Process map') },
};

async function start(el) {
  const data = prepare(await loadJSON('data/soudai.json'));
  const index = searchIndex(data.courts);

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
  const controls = { tab, court };
  // The controls each tab uses, besides the tab switch.
  const USED = { forecast: [court], map: [court] };

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
      current.view.render({ width, height, court: values.court });
      app.status(describe.headline(values.court, data.journey(values.court), data.courts.length));
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
