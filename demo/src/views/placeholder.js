// A tab that isn't built yet: its name, centred on the stage. Every view has the same shape:
// create(host, data) returns { render(state), destroy() }.

import { h } from '../dom.js';

export function createPlaceholder(host, title) {
  const el = h('div', { class: 'sd-placeholder' },
    h('p', { class: 'sd-placeholder-title' }, title),
    h('p', {}, 'Not built yet.'));
  host.append(el);
  return {
    render() {},
    destroy() { el.remove(); },
  };
}
