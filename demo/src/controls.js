// Controls the kit doesn't have, adapted from doctor-who-ratings' demo: a row of buttons for a few
// choices, and a search box with suggestions. Like the kit's controls each returns
// { el, value, disabled, onChange }, so mount() can place it in the rail. Setting `value` updates the
// control without notifying listeners.

import { h } from './dom.js';

let lastId = 0;

/** Optional SVG markup on a 24 × 24 grid, as an icon. */
function icon(markup) {
  if (!markup) return null;
  const span = h('span', { class: 'sd-segment-icon', 'aria-hidden': 'true' });
  span.innerHTML = `<svg viewBox="0 0 24 24" width="20" height="20" focusable="false">${markup}</svg>`;
  return span;
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

  const listeners = new Set();
  const read = () => options[inputs.findIndex((input) => input.checked)]?.value;
  for (const input of inputs) {
    input.addEventListener('change', () => {
      for (const listener of listeners) listener(read());
    });
  }

  return {
    el,
    get value() { return read(); },
    set value(next) {
      const i = options.findIndex((option) => Object.is(option.value, next));
      if (i >= 0) inputs[i].checked = true;
    },
    get disabled() { return el.hasAttribute('data-disabled'); },
    set disabled(state) {
      for (const input of inputs) input.disabled = Boolean(state);
      el.toggleAttribute('data-disabled', Boolean(state));
    },
    onChange(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

/** A round button showing only an icon, with its label for screen readers and as a tooltip. */
export function iconButton({ label, icon: markup }) {
  return h('button', { type: 'button', class: 'dk-button sd-icon-button', 'aria-label': label, title: label }, icon(markup));
}

/**
 * A row of buttons that each do something when pressed, such as adding an event. `options` are
 * { label, value, icon?, iconOnly? }; with `iconOnly`, the button shows its icon alone. The value is
 * the last pressed, and each press notifies, even of the same one. `enable(value, state)` turns one
 * button on or off, and `relabel(value, text)` changes a labelled button's label.
 */
export function actions({ label, options }) {
  const buttons = new Map(options.map((option) => {
    if (option.iconOnly) return [option.value, { el: iconButton(option), text: null }];
    const text = h('span', { class: 'sd-button-label' }, option.label);
    return [option.value, { el: h('button', { type: 'button', class: 'dk-button' }, icon(option.icon), text), text }];
  }));
  const el = h('div', { class: 'dk-control sd-actions', role: 'group', 'aria-label': label }, ...[...buttons.values()].map((b) => b.el));
  const listeners = new Set();
  let last = null;
  for (const [value, { el: press }] of buttons) {
    press.addEventListener('click', () => {
      last = value;
      for (const listener of listeners) listener(value);
    });
  }
  let disabled = false;
  return {
    el,
    get value() { return last; },
    set value(next) { last = next; },
    get disabled() { return disabled; },
    set disabled(state) {
      disabled = Boolean(state);
      for (const { el: press } of buttons.values()) press.disabled = disabled;
      el.toggleAttribute('data-disabled', disabled);
    },
    enable(value, state) {
      const press = buttons.get(value)?.el;
      if (press) press.disabled = disabled || !state;
    },
    relabel(value, text) {
      const target = buttons.get(value)?.text;
      if (target) target.textContent = text;
    },
    onChange(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

/**
 * A search box that suggests matches as you type. `suggest(query)` returns { label, detail, value }s;
 * `format(value)` gives the text to show for a chosen value. With `browse`, focusing or clicking the
 * empty box lists everything `suggest('')` gives. Picking a suggestion, by click, tap or Enter, makes
 * it the value, and clearing the box makes the value null; either notifies. A suggestion whose value
 * is null leaves the box empty, showing the placeholder. The arrow keys move
 * through the suggestions and Escape closes them. `beside` is an element, such as a button, to put to
 * the right of the box; the suggestions then span both.
 */
export function search({ label, placeholder = '', suggest, format, empty = 'No matches', browse = false, beside = null }) {
  const id = `sd-search-${++lastId}`;
  const input = h('input', {
    id,
    type: 'text',
    role: 'combobox',
    'aria-autocomplete': 'list',
    'aria-expanded': 'false',
    'aria-controls': `${id}-list`,
    placeholder,
    autocomplete: 'off',
    spellcheck: 'false',
    enterkeyhint: 'search',
  });
  const clear = h('button', { type: 'button', class: 'sd-search-clear', 'aria-label': 'Clear the search', hidden: true });
  clear.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false"><path d="M7 7l10 10M17 7L7 17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
  const list = h('ul', { id: `${id}-list`, class: 'sd-search-list', role: 'listbox', 'aria-label': label, hidden: true });
  const el = h('div', { class: 'dk-control sd-search' },
    h('label', { for: id, class: 'dk-control-label' }, label),
    h('div', { class: 'sd-search-box' }, h('div', { class: 'sd-search-field' }, input, clear), beside, list));

  const listeners = new Set();
  let chosen = null;
  let results = [];
  let active = -1;

  const notify = () => {
    for (const listener of listeners) listener(chosen);
  };
  const showClear = () => {
    clear.hidden = input.value === '' || input.disabled;
  };

  function close() {
    list.hidden = true;
    results = [];
    active = -1;
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
  }

  function setActive(index) {
    active = index;
    list.querySelectorAll('[role="option"]').forEach((option, i) => option.setAttribute('aria-selected', String(i === active)));
    const option = list.querySelector(`#${id}-option-${active}`);
    if (option) {
      input.setAttribute('aria-activedescendant', option.id);
      option.scrollIntoView({ block: 'nearest' });
    } else {
      input.removeAttribute('aria-activedescendant');
    }
  }

  function open() {
    // While a choice is shown, its text isn't a query: browsing lists everything.
    const query = chosen !== null && input.value === format(chosen) ? '' : input.value.trim();
    if (!query && !browse) {
      close();
      return;
    }
    results = suggest(query);
    list.replaceChildren(...(results.length
      ? results.map((result, i) => {
        const option = h('li', { id: `${id}-option-${i}`, role: 'option', class: 'sd-search-option', 'aria-selected': 'false' },
          h('span', { class: 'sd-search-title' }, result.label),
          result.detail ? h('span', { class: 'sd-search-detail' }, result.detail) : null);
        // Pressing an option would blur the input and close the list before the click lands.
        option.addEventListener('pointerdown', (event) => event.preventDefault());
        option.addEventListener('click', () => choose(i));
        option.addEventListener('pointermove', () => {
          if (active !== i) setActive(i);
        });
        return option;
      })
      : [h('li', { class: 'sd-search-empty', role: 'presentation' }, empty)]));
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
    const current = results.findIndex((result) => Object.is(result.value, chosen));
    setActive(current >= 0 ? current : (results.length ? 0 : -1));
  }

  function choose(index) {
    const result = results[index];
    if (!result) return;
    const changed = !Object.is(result.value, chosen);
    chosen = result.value;
    input.value = chosen === null ? '' : format(chosen);
    showClear();
    close();
    if (changed) notify();
  }

  function reset() {
    input.value = '';
    showClear();
    close();
    if (chosen === null) return;
    chosen = null;
    notify();
  }

  input.addEventListener('input', () => {
    showClear();
    if (input.value.trim() === '' && chosen !== null) {
      reset();
      if (browse) open();
      return;
    }
    open();
  });
  input.addEventListener('focus', () => {
    // Select the shown name, so typing replaces it.
    if (chosen !== null) input.select();
    if (browse) open();
  });
  input.addEventListener('click', () => {
    if (browse && list.hidden) open();
  });
  input.addEventListener('blur', () => {
    close();
    // The box shows what's chosen, so a half-typed search gives way to it.
    input.value = chosen === null ? '' : format(chosen);
    showClear();
  });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (list.hidden) {
        open();
        return;
      }
      if (!results.length) return;
      const step = event.key === 'ArrowDown' ? 1 : -1;
      setActive((active + step + results.length) % results.length);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      if (!list.hidden && active >= 0) choose(active);
    } else if (event.key === 'Escape') {
      if (!list.hidden) {
        event.preventDefault();
        close();
      } else if (input.value) {
        event.preventDefault();
        reset();
      }
    }
  });
  clear.addEventListener('click', () => {
    reset();
    input.focus();
  });

  return {
    el,
    get value() { return chosen; },
    set value(next) {
      chosen = next ?? null;
      input.value = chosen === null ? '' : format(chosen);
      showClear();
      close();
    },
    get disabled() { return input.disabled; },
    set disabled(state) {
      input.disabled = Boolean(state);
      el.toggleAttribute('data-disabled', input.disabled);
      showClear();
    },
    onChange(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
