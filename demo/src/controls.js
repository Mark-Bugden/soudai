// Controls the kit doesn't have: a row of buttons for a few choices (adapted from doctor-who-ratings'
// demo), drop-downs whose options can change, two linked drop-downs, a date, a list whose items can be
// removed, and a drop-down with a date and a button, to add something on that date. Like the kit's
// controls each returns { el, value, disabled, onChange }, so mount() can place it in the rail. Setting
// `value` updates the control without notifying listeners.

import { h } from './dom.js';

let lastId = 0;
const DAY = 864e5;
// A cross, for the buttons that remove something.
const CROSS = '<path d="M7 7l10 10M17 7L7 17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>';

/** Optional SVG markup on a 24 × 24 grid, as an icon. */
function icon(markup, size = 20) {
  if (!markup) return null;
  const span = h('span', { class: 'sd-segment-icon', 'aria-hidden': 'true' });
  span.innerHTML = `<svg viewBox="0 0 24 24" width="${size}" height="${size}" focusable="false">${markup}</svg>`;
  return span;
}

/** A control's listeners: `notify(value)` calls them, and `onChange(listener)` adds one and returns its removal. */
function listeners() {
  const set = new Set();
  return {
    notify(value) {
      for (const listener of set) listener(value);
    },
    onChange(listener) {
      set.add(listener);
      return () => set.delete(listener);
    },
  };
}

/** Turns a control's inputs off or on, marking it for the kit's styles. */
function disable(el, inputs, state) {
  for (const input of inputs) input.disabled = state;
  el.toggleAttribute('data-disabled', state);
}

/**
 * A row of buttons, one per option, of which one is chosen. They're radio buttons underneath, so
 * the arrow keys move between them. `options` are { label, value, icon?, title? }; an icon is SVG
 * markup on a 24 × 24 grid. `showLabel: false` leaves the label to screen readers.
 */
export function segmented({ label, options, value = options[0].value, showLabel = true }) {
  const id = `sd-segmented-${++lastId}`;
  const inputs = options.map((option, i) => h('input', { type: 'radio', name: id, value: i, checked: Object.is(option.value, value) }));
  const segments = options.map((option, i) => h('label', { class: 'sd-segment', title: option.title },
    inputs[i], icon(option.icon), h('span', { class: 'sd-segment-label' }, option.label)));
  const el = h('div', {
    class: `dk-control sd-segmented${options.some((o) => o.icon) ? ' sd-segmented-icons' : ''}`,
    role: 'radiogroup',
    'aria-labelledby': `${id}-label`,
  }, h('span', { id: `${id}-label`, class: showLabel ? 'dk-control-label' : 'sd-sr-only' }, label), h('div', { class: 'sd-segments' }, ...segments));

  const { notify, onChange } = listeners();
  const read = () => options[inputs.findIndex((input) => input.checked)]?.value;
  for (const input of inputs) input.addEventListener('change', () => notify(read()));

  return {
    el,
    get value() { return read(); },
    set value(next) {
      const i = options.findIndex((option) => Object.is(option.value, next));
      if (i >= 0) inputs[i].checked = true;
    },
    get disabled() { return el.hasAttribute('data-disabled'); },
    set disabled(state) { disable(el, inputs, Boolean(state)); },
    onChange,
  };
}

/** A round button showing only an icon, with its label for screen readers and as a tooltip. */
export function iconButton({ label, icon: markup }) {
  return h('button', { type: 'button', class: 'dk-button sd-icon-button', 'aria-label': label, title: label }, icon(markup));
}

/**
 * Fills a select with `options`, which are { label, value }, or { group, options } for a labelled group
 * of them, and returns their values in the order it lists them.
 */
function fill(select, options) {
  const values = [];
  const option = ({ label, value }) => h('option', { value: values.push(value) - 1 }, label);
  select.replaceChildren(...options.map((item) => (item.group
    ? h('optgroup', { label: item.group }, ...item.options.map(option))
    : option(item))));
  return values;
}

/**
 * A drop-down whose options can change: `setOptions(options, value)` replaces them and chooses `value`.
 * Options are { label, value }, or { group, options } for a labelled group of them. `beside` is an
 * element, such as a button, to put to the right of it.
 */
export function dropdown({ label, options = [], value, beside = null }) {
  const id = `sd-dropdown-${++lastId}`;
  const select = h('select', { id });
  let values = fill(select, options);
  const write = (next) => {
    const i = values.findIndex((v) => Object.is(v, next));
    if (i >= 0) select.selectedIndex = i;
  };
  if (value !== undefined) write(value);
  const el = h('div', { class: 'dk-control dk-select' },
    h('label', { for: id, class: 'dk-control-label' }, label),
    beside ? h('div', { class: 'sd-beside' }, select, beside) : select);
  const { notify, onChange } = listeners();
  select.addEventListener('change', () => notify(values[select.selectedIndex]));
  return {
    el,
    get value() { return values[select.selectedIndex]; },
    set value(next) { write(next); },
    get disabled() { return el.hasAttribute('data-disabled'); },
    set disabled(state) { disable(el, [select], Boolean(state)); },
    setOptions(next, chosen) {
      values = fill(select, next);
      write(chosen);
    },
    onChange,
  };
}

/**
 * Two drop-downs under one label, such as a court's type and then its place: the second lists only the
 * options of the group chosen in the first, and choosing a group chooses its first option. `groups` are
 * { label, options: [{ label, value }] }, and `names` the two drop-downs' names, for screen readers.
 * With `none`, a label such as "All courts", the first also offers that: it hides the second, and makes
 * the value null. `offerNone(state)` adds or takes it away; give a value before taking it away.
 */
export function cascade({ label, groups, names: [groupName, optionName], value = null, none = null }) {
  const id = `sd-cascade-${++lastId}`;
  const first = h('select', { 'aria-label': groupName });
  const second = h('select', { 'aria-label': optionName });
  const el = h('div', { class: 'dk-control dk-select sd-cascade', role: 'group', 'aria-labelledby': `${id}-label` },
    h('span', { id: `${id}-label`, class: 'dk-control-label' }, label), first, second);
  const { notify, onChange } = listeners();
  let offered = Boolean(none);
  let chosen = value;
  const groupOf = (v) => groups.findIndex((group) => group.options.some((option) => Object.is(option.value, v)));

  /** Shows the value: its group in the first drop-down, and the group's options in the second. */
  function show() {
    const g = chosen === null ? -1 : groupOf(chosen);
    first.value = g < 0 ? 'none' : String(g);
    second.hidden = g < 0;
    if (g < 0) return;
    const { options } = groups[g];
    if (second.dataset.group !== String(g)) {
      second.replaceChildren(...options.map((option, i) => h('option', { value: i }, option.label)));
      second.dataset.group = String(g);
    }
    second.selectedIndex = options.findIndex((option) => Object.is(option.value, chosen));
  }

  function offer(state) {
    offered = state;
    first.replaceChildren(
      ...(offered ? [h('option', { value: 'none' }, none)] : []),
      ...groups.map((group, i) => h('option', { value: i }, group.label)),
    );
    show();
  }

  first.addEventListener('change', () => {
    chosen = first.value === 'none' ? null : groups[Number(first.value)].options[0].value;
    show();
    notify(chosen);
  });
  second.addEventListener('change', () => {
    chosen = groups[Number(first.value)].options[second.selectedIndex].value;
    notify(chosen);
  });
  offer(offered);

  return {
    el,
    get value() { return chosen; },
    set value(next) {
      chosen = next ?? null;
      show();
    },
    get disabled() { return el.hasAttribute('data-disabled'); },
    set disabled(state) { disable(el, [first, second], Boolean(state)); },
    offerNone(state) {
      if (none && Boolean(state) !== offered) offer(Boolean(state));
    },
    onChange,
  };
}

/** "2024-06-03", a date input's value, for a date at midnight UTC. */
const iso = (date) => date.toISOString().slice(0, 10);

/**
 * A date input, with the browser's own calendar, whose value is a date at midnight UTC. `range(min, max)`
 * limits it (either may be null), and moves the value into the range. A date picked or typed within the
 * range notifies at once. When the box loses focus, a date outside the range is moved into it, and an
 * empty box gives way to the last date.
 */
function dateInput({ value, ...attributes }) {
  const input = h('input', { type: 'date', ...attributes });
  const { notify, onChange } = listeners();
  let current = value;
  let low = null;
  let high = null;
  const clamp = (date) => new Date(Math.min(Math.max(date.getTime(), low?.getTime() ?? -Infinity), high?.getTime() ?? Infinity));
  const typed = () => (Number.isNaN(input.valueAsNumber) ? null : new Date(Math.round(input.valueAsNumber / DAY) * DAY));
  const accept = (date) => {
    input.value = iso(date);
    if (date.getTime() === current.getTime()) return;
    current = date;
    notify(current);
  };
  input.value = iso(current);
  input.addEventListener('change', () => {
    const date = typed();
    if (date && date.getTime() === clamp(date).getTime()) accept(date);
  });
  input.addEventListener('blur', () => {
    const date = typed();
    accept(date ? clamp(date) : current);
  });
  return {
    input,
    get value() { return current; },
    set value(next) {
      current = clamp(next);
      input.value = iso(current);
    },
    range(min, max) {
      low = min;
      high = max;
      input.min = min ? iso(min) : '';
      input.max = max ? iso(max) : '';
      this.value = current;
    },
    onChange,
  };
}

/**
 * A labelled date, with the browser's own calendar: see dateInput. Its value is a date at midnight UTC.
 * The label is beside the date, which goes below it where there isn't room.
 */
export function dateField({ label, value }) {
  const id = `sd-date-${++lastId}`;
  const date = dateInput({ id, value });
  const el = h('div', { class: 'dk-control sd-date' }, h('label', { for: id, class: 'dk-control-label' }, label), date.input);
  return {
    el,
    get value() { return date.value; },
    set value(next) { date.value = next; },
    range: (min, max) => date.range(min, max),
    get disabled() { return el.hasAttribute('data-disabled'); },
    set disabled(state) { disable(el, [date.input], Boolean(state)); },
    onChange: date.onChange,
  };
}

/**
 * Text in the rail under a label, such as what the methods on a chart are: `items` are { term, about }.
 * It changes nothing, so it has no value and never notifies.
 */
export function notes({ label, items }) {
  const el = h('div', { class: 'dk-control' },
    h('span', { class: 'dk-control-label' }, label),
    h('dl', { class: 'sd-notes' }, ...items.flatMap(({ term, about }) => [h('dt', {}, term), h('dd', {}, about)])));
  return { el, value: null, onChange: () => () => {} };
}

/**
 * A list whose items each have a button to remove them, with its label for screen readers only. Setting
 * `items` shows { when, what }s; pressing
 * an item's button notifies with its index, and the value is the index last removed. When the items next
 * change, the button in the same place, or else the last, takes the focus, so it isn't lost.
 */
export function removable({ label }) {
  const id = `sd-list-${++lastId}`;
  const list = h('ul', { class: 'sd-list', 'aria-labelledby': `${id}-label` });
  const el = h('div', { class: 'dk-control sd-removable' }, h('span', { id: `${id}-label`, class: 'sd-sr-only' }, label), list);
  const { notify, onChange } = listeners();
  let last = null;
  let refocus = null;
  return {
    el,
    get value() { return last; },
    set value(next) { last = next; },
    set items(rows) {
      const buttons = rows.map(({ when, what }, i) => {
        const button = h('button', { type: 'button', class: 'sd-remove', 'aria-label': `Remove ${what}, ${when}`, title: 'Remove' }, icon(CROSS, 16));
        button.addEventListener('click', () => {
          last = i;
          refocus = i;
          notify(i);
        });
        return button;
      });
      list.replaceChildren(...rows.map(({ when, what }, i) => h('li', { class: 'sd-list-item' },
        h('span', { class: 'sd-list-when' }, when), h('span', { class: 'sd-list-what' }, what), buttons[i])));
      if (refocus !== null) buttons[Math.min(refocus, buttons.length - 1)]?.focus();
      refocus = null;
    },
    get disabled() { return el.hasAttribute('data-disabled'); },
    set disabled(state) { disable(el, list.querySelectorAll('button'), Boolean(state)); },
    onChange,
  };
}

/**
 * A drop-down of things to add, a date, and an "Add" button, which notifies with { option, date }: the
 * value of the option chosen, and the date. `options` are { label, value }, and `dateLabel` names the
 * date for screen readers. `range(min, max)` limits the date, and `enable(test)` turns the button on for
 * the options that pass the test, and off for the others.
 */
export function adder({ label, options, date: value, dateLabel }) {
  const id = `sd-adder-${++lastId}`;
  const select = h('select', { id });
  const values = fill(select, options);
  const date = dateInput({ value, 'aria-label': dateLabel });
  const button = h('button', { type: 'button', class: 'dk-button' }, 'Add');
  const el = h('div', { class: 'dk-control dk-select sd-adder' },
    h('label', { for: id, class: 'dk-control-label' }, label), select, h('div', { class: 'sd-beside' }, date.input, button));
  const { notify, onChange } = listeners();
  let last = null;
  let test = () => true;
  const update = () => {
    button.disabled = el.hasAttribute('data-disabled') || !test(values[select.selectedIndex]);
  };
  select.addEventListener('change', update);
  button.addEventListener('click', () => {
    // A date typed but not yet checked is checked first.
    date.input.blur();
    last = { option: values[select.selectedIndex], date: date.value };
    notify(last);
  });
  return {
    el,
    get value() { return last; },
    set value(next) { last = next; },
    range: (min, max) => date.range(min, max),
    get disabled() { return el.hasAttribute('data-disabled'); },
    set disabled(state) {
      disable(el, [select, date.input], Boolean(state));
      update();
    },
    enable(next) {
      test = next;
      update();
    },
    onChange,
  };
}
