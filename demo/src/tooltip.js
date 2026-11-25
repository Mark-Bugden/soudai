// The tooltip: a few lines beside the mark they describe, the first in bold. Adapted from
// doctor-who-ratings' demo. It's hidden from screen readers, because the status line and the view's
// hidden list say the same.

import { h } from './dom.js';

const GAP = 10;
const EDGE = 6;

export function createTooltip(container) {
  const el = h('div', { class: 'sd-tip', 'aria-hidden': 'true', hidden: true });
  container.append(el);

  return {
    /** Shows `lines` (the first in bold) beside the point { x, y } in the container, kept inside it. */
    show(lines, { x, y }) {
      el.replaceChildren(h('strong', {}, lines[0]), ...lines.slice(1).map((line) => h('span', {}, line)));
      el.hidden = false;
      const { width, height } = container.getBoundingClientRect();
      const box = el.getBoundingClientRect();
      const left = Math.min(Math.max(EDGE, x - box.width / 2), width - box.width - EDGE);
      const above = y - box.height - GAP;
      const top = above >= EDGE ? above : Math.min(y + GAP, height - box.height - EDGE);
      el.style.transform = `translate(${Math.round(left)}px, ${Math.round(top)}px)`;
    },
    hide() {
      el.hidden = true;
    },
    destroy() {
      el.remove();
    },
  };
}
