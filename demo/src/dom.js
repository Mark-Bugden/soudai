// Small DOM helpers for the views.

const SVG = 'http://www.w3.org/2000/svg';

function build(el, attributes, children) {
  for (const [name, value] of Object.entries(attributes)) {
    if (value === false || value == null) continue;
    el.setAttribute(name, value === true ? '' : String(value));
  }
  el.append(...children.filter((child) => child != null && child !== false));
  return el;
}

/** Creates an HTML element. Attributes set to false or null are skipped; true sets an empty attribute. */
export const h = (tag, attributes = {}, ...children) => build(document.createElement(tag), attributes, children);

/** Creates an SVG element, in the same way. */
export const s = (tag, attributes = {}, ...children) => build(document.createElementNS(SVG, tag), attributes, children);
