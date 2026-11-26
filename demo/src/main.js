// The demo's entry point. Vite bundles it with the kit and the CSS into demo.js and demo.css.
//
// It loads the data, then mounts the frame with the controls, showing only those the current tab uses.
// The tabs (views/) draw the stage; this module keeps the state they share: the tab, the court
// selected (or none, for all courts), and on the Forecast tab either a case, real or made up, with the
// day of its forecast, or how well the model does. The status line shows what's selected, with its
// headline numbers.

import manifest from 'virtual:manifest';
import { loadJSON, mount, select, slider } from '@mark-bugden/demo-kit';
import '@mark-bugden/demo-kit/tokens.scoped.css';
import '@mark-bugden/demo-kit/frame.css';
import './demo.css';
import { MOST_EVENTS, add, findCases, madeUp, offered, ordered, pick, undo } from './cases.js';
import { actions, search, segmented } from './controls.js';
import { matches, searchIndex } from './courts.js';
import { prepare } from './data.js';
import { h } from './dom.js';
import * as describe from './format.js';
import { LANDMARKS } from './scores.js';
import { createForecast } from './views/forecast.js';
import { createMap } from './views/map.js';
import { createScores } from './views/scores.js';

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
  forecast: { label: 'Forecast' },
  map: { label: 'Process map' },
};
// What each tab draws: the Forecast tab shows a case or the scores.
const VIEWS = {
  forecast: { label: 'Forecast', create: createForecast },
  scores: { label: 'How well it does', create: createScores },
  map: { label: 'Process map', create: createMap },
};
// The case the demo opens on: an ordinary one, with a hearing and a decision.
const OPENING = { court: 'OSJIMJI', label: '18 C 33/2024' };
const MADE_UP_DAYS = 1096; // a made-up case's forecast can be up to 36 months after filing

async function start(el) {
  const data = prepare(await loadJSON('data/soudai.json'));
  const index = searchIndex(data.courts);
  // Every real case, by court in order of area, then by number.
  const allCases = ordered(data.cases, index.map((entry) => entry.court));
  const casesOf = (court) => (court ? ordered(court.cases, [court]) : allCases);
  let item = data.court(OPENING.court).cases.find((c) => c.label === OPENING.label) ?? data.cases[0];
  let made = madeUp(data, null); // its court is the one selected
  const events = offered(data);

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
  const show = segmented({
    label: 'Show',
    options: [{ label: 'A case', value: 'case' }, { label: 'How well it does', value: 'scores' }],
    value: 'case',
  });
  const kind = segmented({
    label: 'Case',
    options: [{ label: 'Real', value: 'real', title: 'A real past case' }, { label: 'Made up', value: 'made', title: 'A case you describe' }],
    value: 'real',
  });
  const realCase = search({
    label: 'Case number',
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
  const random = actions({ label: 'Pick a case', options: [{ label: 'Random case', value: 'random', icon: ICONS.random }] });
  const day = slider({
    label: 'Forecast on',
    min: 0,
    max: item.span - 1,
    step: 1,
    value: 0,
    format: (d) => (d === 0 ? `Filing, ${describe.date(item.filed, true)}` : `Day ${describe.count(d)}, ${describe.date(describe.addDays(item.filed, d), true)}`),
  });
  const madeDay = slider({
    label: 'Forecast on',
    min: 0,
    max: MADE_UP_DAYS,
    step: 1,
    value: 0,
    format: (d) => (d === 0 ? 'Filing' : `Day ${describe.count(d)}`),
  });
  const event = select({ label: 'Event', options: events.map((option) => ({ label: option.label, value: option })) });
  const addEvent = actions({ label: 'Add the event', options: [{ label: 'Add', value: 'add' }] });
  const edit = actions({ label: 'Change the case', options: [{ label: 'Undo', value: 'undo' }, { label: 'Start again', value: 'reset' }] });
  const landmark = segmented({
    label: 'Forecasts made, months after filing',
    options: LANDMARKS.map((when) => ({ label: when === 'all' ? 'All' : when, value: when, title: when === 'all' ? 'All forecasts together' : describe.landmark(when) })),
    value: 'all',
  });
  const horizon = segmented({
    label: 'Calibration within, months',
    options: data.horizons.map((months) => ({ label: String(months), value: months, title: `Within ${describe.months(months)}` })),
    value: 6,
  });
  const controls = { tab, court, show, kind, realCase, random, day, madeDay, event, addEvent, edit, landmark, horizon };
  // The controls each tab uses, besides the tab switch.
  const used = () => {
    if (tab.value === 'map') return [court];
    if (show.value === 'scores') return [court, show, landmark, horizon];
    return [court, show, kind, ...(kind.value === 'real' ? [realCase, random, day] : [madeDay, event, addEvent, edit])];
  };

  /** Sets a slider's range, keeping its value within it. */
  function range(control, min, max) {
    const input = control.el.querySelector('input');
    input.min = String(min);
    input.max = String(max);
    control.value = Math.min(Math.max(control.value, min), max);
  }

  /** Shows a real case, from its filing. */
  function choose(next) {
    item = next;
    realCase.value = item;
    day.value = 0;
    range(day, 0, item.span - 1);
  }

  /** Changes the made-up case. Its forecast can't come before its last event. */
  function change(next) {
    made = next;
    range(madeDay, made.events.at(-1).day, MADE_UP_DAYS);
  }
  choose(item);
  // A court that isn't the case's brings one of its own cases.
  court.onChange((c) => {
    if (c && item.court !== c) choose(pick(casesOf(c)));
  });
  // Clearing the case box leaves the case as it was.
  realCase.onChange((c) => (c ? choose(c) : (realCase.value = item)));
  random.onChange(() => choose(pick(casesOf(court.value), item)));
  addEvent.onChange(() => change(add(made, event.value.codes, madeDay.value)));
  edit.onChange((action) => {
    change(action === 'undo' ? undo(made) : madeUp(data, null));
    if (action === 'reset') madeDay.value = 0;
  });

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
      const name = values.tab === 'forecast' && values.show === 'scores' ? 'scores' : values.tab;
      if (current?.name !== name) {
        current?.view.destroy();
        current = { name, view: VIEWS[name].create(host, data) };
        stage.setAttribute('aria-label', VIEWS[name].label);
        // On phones the stage grows to fit the scores and the map (see demo.css).
        stage.closest('.dk-stage').classList.toggle('sd-fit-content', name !== 'forecast');
      }
      showControls();
      // A court's scores are for all its forecasts together.
      landmark.disabled = Boolean(values.court);
      if (values.court) landmark.value = 'all';
      const real = values.kind === 'real';
      if (!real) showEditing();
      const status = current.view.render({
        width,
        height,
        court: values.court,
        item: real ? item : { ...made, court: values.court },
        day: real ? values.day : values.madeDay,
        landmark: values.landmark,
        horizon: values.horizon,
      });
      app.status(status ?? describe.headline(values.court, data.journey(values.court), data.courts.length));
    },
  });
  app.stage.setAttribute('role', 'region');
  el.querySelector('.dk-status')?.setAttribute('aria-live', 'polite');
  // Before the first draw, so the controls the opening tab doesn't use never show.
  showControls();

  /** Shows the controls the tab uses, and hides the rest. */
  function showControls() {
    const shown = new Set([tab, ...used()]);
    for (const control of Object.values(controls)) control.el.hidden = !shown.has(control);
  }

  /** Labels the made-up case's buttons for the day, and turns off those that can't do anything. */
  function showEditing() {
    addEvent.relabel('add', madeDay.value === 0 ? 'Add at filing' : `Add on day ${describe.count(madeDay.value)}`);
    addEvent.enable('add', made.events.length + event.value.codes.length <= MOST_EVENTS);
    edit.enable('undo', made.added.length > 0);
    edit.enable('reset', made.added.length > 0);
  }
}

const el = document.querySelector(`[data-demo="${manifest.slug}"]`);
start(el).catch((error) => {
  // The still image stays in place.
  console.error('soudai: could not start the demo', error);
});
