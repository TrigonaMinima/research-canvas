// The contents list of one box, built from the sections sections.js already made. It
// lives outside [data-body], so nothing here can shift an anchor's offsets, and every
// entry is written with textContent: heading text is the document's, not ours to trust.

import { MIN_TOC_HEADINGS, TOC_MAX_LEVEL } from './config.js';

// Only a heading that heads a section: sectionize moved every one of them, so a
// heading anywhere else is inside a blockquote or a list, and not an outline.
const LISTED = Array.from({ length: TOC_MAX_LEVEL }, (_, i) => `[data-sec] > h${i + 1}`).join(',');

function entry(heading) {
  const li = document.createElement('li');
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'box__toc-entry';
  button.dataset.tocKey = heading.parentElement.dataset.sec;
  // The chevron inside the heading has no text, so this is the heading's words alone.
  button.textContent = heading.textContent.trim();
  li.append(button);
  return li;
}

// Rebuilds the list from a freshly sectionized body. Too few headings leaves it empty,
// which is the caller's signal to hide the whole strip.
export function build(tocEl, bodyEl) {
  const list = tocEl.querySelector('[data-toc-list]');
  const headings = [...bodyEl.querySelectorAll(LISTED)];
  list.replaceChildren();
  if (headings.length < MIN_TOC_HEADINGS) return;

  // sectionize already nested the sections by level, so the list follows that outline
  // rather than working it out again. A listed section's parent section is always a
  // listed one: only a shallower heading can hold it.
  const entries = new Map();
  for (const heading of headings) {
    const section = heading.parentElement;
    const parent = entries.get(section.parentElement.closest('[data-sec]'));
    const into = parent
      ? parent.querySelector(':scope > ol') ?? parent.appendChild(document.createElement('ol'))
      : list;
    const li = entry(heading);
    into.append(li);
    entries.set(section, li);
  }
  tocEl.querySelector('[data-toc-count]').textContent = String(headings.length);
}

export function clear(tocEl) {
  tocEl.querySelector('[data-toc-list]').replaceChildren();
}
