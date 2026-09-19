// Every markdown heading is the head of a section that folds on its own, nested by
// level. The structure is built here, in the browser, by moving the nodes markdown-it
// already produced.
//
// An anchor is a character offset into this body's rendered plain text, so the
// transform is only ever allowed to move existing nodes and insert empty wrappers.
// Handing a wrapper collected HTML would renormalise the `\n` text nodes between
// blocks and silently drift every stored anchor. For the same reason no control in
// here carries a text node: the chevron's glyph is a CSS `content` and its name an
// `aria-label`.

const HEADING = /^H([1-6])$/;
const KEY_MAX = 60;
const FOLD = 'Fold this section';
const UNFOLD = 'Unfold this section';

// 0 for anything that is not a heading, so the one pass below can ask any node it
// meets, text and comment nodes included.
function levelOf(node) {
  if (node.nodeType !== Node.ELEMENT_NODE) return 0;
  const match = HEADING.exec(node.tagName);
  return match ? Number(match[1]) : 0;
}

// A slug of the heading's own words rather than an ordinal: an ordinal shifts the
// moment a heading is inserted, which would fold the wrong sections after an edit.
// The level is deliberately left out, so a heading promoted from h3 to h2 keeps its
// fold. A repeat gets `-2`, `-3` from the per-body counter.
function keyFor(heading, seen) {
  const slug = heading.textContent
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .slice(0, KEY_MAX)
    .replace(/^-+|-+$/g, '');
  const base = slug || 'section';
  const nth = (seen.get(base) || 0) + 1;
  seen.set(base, nth);
  return nth === 1 ? base : `${base}-${nth}`;
}

// The three attributes that say which way the chevron points, in one place so the
// build and every later fold cannot disagree. Mirrors the box fold in boxes.js.
function say(toggle, collapsed) {
  const label = collapsed ? UNFOLD : FOLD;
  toggle.setAttribute('aria-expanded', String(!collapsed));
  toggle.setAttribute('aria-label', label);
  toggle.title = label;
}

function chevron(id) {
  const el = document.createElement('button');
  el.type = 'button';
  el.className = 'sec__fold';
  el.dataset.secToggle = '';
  el.setAttribute('aria-controls', id);
  say(el, false);
  return el;
}

// Moves the heading into a fresh section and hands back the body the nodes after it
// belong in.
function build(heading, boxId, seen) {
  const key = keyFor(heading, seen);

  const el = document.createElement('section');
  el.className = 'sec';
  el.dataset.sec = key;

  const body = document.createElement('div');
  body.className = 'sec__body';
  body.dataset.secBody = '';
  // The id carries the box, because the same heading text in the document and in an
  // answer would otherwise share one id and fail the standards check.
  body.id = `sec-${boxId}-${key}`;

  el.append(heading, body);
  // Last, so the key above was read off the heading's text alone.
  heading.prepend(chevron(body.id));
  return { el, body };
}

// One pass, with a stack of the sections still open. Runs exactly once per innerHTML
// assignment, on a freshly written body, and has no idempotence guard on purpose: a
// guard keyed on an existing [data-sec] could only ever skip headings that arrived in
// a rebuild.
export function sectionize(bodyEl, boxId) {
  const nodes = [...bodyEl.childNodes]; // a snapshot: the pass moves them
  const seen = new Map();
  const stack = [];

  for (const node of nodes) {
    const level = levelOf(node);
    if (level) {
      // A heading closes every open section of its own level or deeper.
      while (stack.length && stack.at(-1).level >= level) stack.pop();
      const section = build(node, boxId, seen);
      (stack.at(-1)?.body ?? bodyEl).append(section.el);
      stack.push({ level, body: section.body });
    } else if (stack.length) {
      // Content and whitespace alike: a blank text node travels with the block that
      // follows it, so the body's text comes out in the order it went in.
      stack.at(-1).body.append(node);
    }
    // Before the first heading: left exactly where it is.
  }
}

// Project the folded keys onto the sections, and hand back the ones that landed.
// Every section is visited, not just the listed ones, so unfolding is carried across a
// rebuild as faithfully as folding. A key matching no section is dropped from the
// return: that is how a heading edited away leaves the model, on the reader's next
// fold. The renderer ignores the return, so rendering never writes the model.
export function apply(bodyEl, keys) {
  const folded = new Set(keys || []);
  const matched = [];

  for (const el of bodyEl.querySelectorAll('[data-sec]')) {
    const collapsed = folded.has(el.dataset.sec);
    if (collapsed) matched.push(el.dataset.sec);

    // The flag goes on the body, the one node the fold hides, and not on the section,
    // which still holds the heading. find.js rejects the subtree under whatever wears
    // this attribute, so a folded heading stays findable while its contents do not.
    const body = el.querySelector(':scope > [data-sec-body]');
    if (!body) continue;
    if (collapsed) body.dataset.collapsed = '1';
    else delete body.dataset.collapsed;

    // build() prepends the chevron into the heading, so it is the first element child
    // of the first. Matching keeps the read as forgiving as a query was.
    const toggle = el.firstElementChild?.firstElementChild;
    if (toggle?.matches('[data-sec-toggle]')) say(toggle, collapsed);
  }

  return matched;
}

export function keyOf(toggleEl) {
  return toggleEl.closest('[data-sec]')?.dataset.sec ?? null;
}

// The hidden bodies in one body, outermost first, and the sections they head. Both
// repairs below ask about the hidden body rather than the section, because a folded
// section's heading is still on screen. A folded section inside another comes back on
// its own, since opening only the outer one would leave the inner text hidden.
function foldedBodies(bodyEl) {
  return [...bodyEl.querySelectorAll('[data-sec] > [data-sec-body][data-collapsed="1"]')];
}

const keysOf = (bodies) => bodies.map((body) => body.parentElement.dataset.sec);

// The folded sections a selection runs through, so a quote never covers hidden text.
export function crossedBy(bodyEl, range) {
  return keysOf(foldedBodies(bodyEl).filter((body) => range.intersectsNode(body)));
}

// The folded sections a node sits behind, for the way back to a hidden passage.
export function holding(bodyEl, node) {
  return keysOf(foldedBodies(bodyEl).filter((body) => body.contains(node)));
}
