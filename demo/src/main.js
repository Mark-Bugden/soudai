// The demo's entry point. Vite bundles it with the kit and the CSS into demo.js and demo.css.
//
// It loads the data, then mounts the frame with the controls, showing only those the current tab uses.
// The tabs (views/) draw the stage; this module keeps the state they share: the tab, and the court
// selected, or none for all courts. The Forecast tab always has a court: the one selected, or else the
// last it had. Its case is one of that court's real past cases, with the day of its forecast, or a
// custom case, whose filing, events and day of forecast the visitor gives as dates. The status line
// shows what's selected, with its headline numbers.

import manifest from 'virtual:manifest';
import { loadJSON, mount, slider } from '@mark-bugden/demo-kit';
import '@mark-bugden/demo-kit/tokens.scoped.css';
import '@mark-bugden/demo-kit/frame.css';
import './demo.css';
import { LONGEST, MOST_EVENTS, add, custom, filingRange, offered, ordered, pick, refile, remove } from './cases.js';
import { adder, cascade, dateField, dropdown, iconButton, removable, segmented } from './controls.js';
import { byType } from './courts.js';
import { prepare } from './data.js';
import { h } from './dom.js';
import * as describe from './format.js';
import { createForecast } from './views/forecast.js';
import { createMap } from './views/map.js';

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
  map: { label: 'Process map', create: createMap },
};
// The case the demo opens on: an ordinary one, with a hearing and a decision.
const OPENING = { court: 'OSJIMJI', label: '18 C 33/2024' };
const CUSTOM = 'custom'; // the case menu's value for a custom case
const DAY = 864e5;

/** Today where the visitor is, as a date at midnight UTC. */
function today() {
  const now = new Date();
  return new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
}

/** Days from one date at midnight UTC to another. */
const daysBetween = (from, to) => Math.round((to - from) / DAY);

async function start(el) {
  const data = prepare(await loadJSON('data/soudai.json'));
  let selected = null; // the court selected, or null for all courts
  let forecastCourt = data.court(OPENING.court); // the Forecast tab's: the one selected, or the last it had
  let item = forecastCourt.cases.find((c) => c.label === OPENING.label) ?? forecastCourt.cases[0];
  let made = custom(data, forecastCourt, today());

  const tab = segmented({
    label: 'View',
    showLabel: false,
    options: Object.entries(TABS).map(([value, { label }]) => ({ label, value, icon: ICONS[value] })),
    value: 'forecast',
  });
  // A court's type, then its place. Only the Process map offers all courts.
  const court = cascade({
    label: 'Court',
    names: ['Court type', 'Location'],
    groups: byType(data.courts).map(({ type, courts }) => ({ label: type, options: courts.map(({ court: c, place }) => ({ label: place, value: c })) })),
    value: forecastCourt,
    none: 'All courts',
  });
  court.offerNone(false);
  // The court's real past cases, and a custom case. The die beside the menu picks a real one at random.
  const random = iconButton({ label: 'Random case', icon: ICONS.random });
  const caseMenu = dropdown({ label: 'Case', beside: random });
  const day = slider({
    label: 'Forecast on',
    min: 0,
    max: item.span - 1,
    step: 1,
    value: 0,
    format: (d) => (d === 0 ? `Filing, ${describe.date(item.filed, true)}` : `Day ${describe.count(d)}, ${describe.date(describe.addDays(item.filed, d), true)}`),
  });
  const filedOn = dateField({ label: 'Filed on', value: made.filed });
  const eventList = removable({ label: 'Events' });
  const addEvent = adder({
    label: 'Add an event',
    options: offered(data).map((option) => ({ label: option.label, value: option })),
    date: made.filed,
    dateLabel: 'Date of the event',
  });
  const forecastOn = dateField({ label: 'Forecast on', value: made.filed });
  const controls = { tab, court, caseMenu, day, filedOn, eventList, addEvent, forecastOn };
  // The controls each tab uses, besides the tab switch.
  const used = () => {
    if (tab.value === 'map') return [court];
    if (caseMenu.value !== CUSTOM) return [court, caseMenu, day];
    return [court, caseMenu, filedOn, ...(made.events.length > 1 ? [eventList] : []), addEvent, forecastOn];
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
    day.value = 0;
    range(day, 0, item.span - 1);
  }

  /** Lists the Forecast tab's court's cases in the case menu, and shows the case chosen. */
  function listCases() {
    caseMenu.setOptions([
      { label: 'Custom case', value: CUSTOM },
      { group: 'Real past cases', options: ordered(forecastCourt.cases).map((c) => ({ label: c.label, value: c })) },
    ], caseMenu.value === CUSTOM ? CUSTOM : item);
  }

  /**
   * Fits the custom case's controls to it: its filing can't come after its first event or more than 36
   * months before its last, its events go between its filing and 36 months after, and its forecast
   * between its last event and 36 months after its filing.
   */
  function fitCustom() {
    const at = (d) => (Number.isFinite(d) ? describe.addDays(made.filed, d) : null);
    filedOn.range(...filingRange(made).map(at));
    filedOn.value = made.filed;
    addEvent.range(made.filed, at(LONGEST));
    addEvent.enable((option) => made.events.length + option.codes.length <= MOST_EVENTS);
    forecastOn.range(at(made.events.at(-1).day), at(LONGEST));
    eventList.items = made.events.slice(1).map((event) => ({ when: describe.date(at(event.day), true), what: event.code.gloss }));
  }

  choose(item);
  listCases();
  fitCustom();
  // The Process map offers all courts, and the Forecast tab shows its own court when none is selected.
  tab.onChange((name) => {
    if (name === 'map') {
      court.offerNone(true);
      court.value = selected;
    } else {
      court.value = forecastCourt;
      court.offerNone(false);
    }
  });
  // A court that isn't the case's brings one of its own cases, and a custom case moves to it.
  court.onChange((c) => {
    selected = c;
    if (!c) return;
    forecastCourt = c;
    made = { ...made, court: c };
    if (item.court !== c) choose(pick(c.cases));
    listCases();
  });
  caseMenu.onChange((value) => {
    if (value !== CUSTOM) choose(value);
  });
  // The button isn't one of the frame's controls, so it asks for the redraw itself.
  random.addEventListener('click', () => {
    choose(pick(forecastCourt.cases, caseMenu.value === CUSTOM ? null : item));
    caseMenu.value = item;
    app.redraw();
  });
  filedOn.onChange((date) => {
    made = refile(made, daysBetween(made.filed, date));
    fitCustom();
  });
  eventList.onChange((i) => {
    made = remove(made, i + 1);
    fitCustom();
  });
  addEvent.onChange(({ option, date }) => {
    made = add(made, option.codes, daysBetween(made.filed, date));
    fitCustom();
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
      const name = values.tab;
      if (current?.name !== name) {
        current?.view.destroy();
        current = { name, view: TABS[name].create(host, data) };
        stage.setAttribute('aria-label', TABS[name].label);
        // On phones the stage grows to fit the map, and the Forecast tab's status line is for screen
        // readers only (see demo.css).
        stage.closest('.dk-stage').classList.toggle('sd-fit-content', name !== 'forecast');
        el.classList.toggle('sd-hide-status', name === 'forecast');
      }
      showControls();
      const isCustom = values.caseMenu === CUSTOM;
      const status = current.view.render({
        width,
        height,
        court: values.court,
        item: isCustom ? made : item,
        day: isCustom ? daysBetween(made.filed, values.forecastOn) : values.day,
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
}

const el = document.querySelector(`[data-demo="${manifest.slug}"]`);
start(el).catch((error) => {
  // The still image stays in place.
  console.error('soudai: could not start the demo', error);
});
