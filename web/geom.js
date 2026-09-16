// Shapes the two SVG layers both need. One definition each.

export const svg = (name, attrs) => {
  const el = document.createElementNS('http://www.w3.org/2000/svg', name);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
  return el;
};

// The rectangle every box sits inside, optionally padded.
export function bounds(boxes, pad = 0) {
  return {
    x0: Math.min(...boxes.map((b) => b.x)) - pad,
    y0: Math.min(...boxes.map((b) => b.y)) - pad,
    x1: Math.max(...boxes.map((b) => b.x + b.w)) + pad,
    y1: Math.max(...boxes.map((b) => b.y + b.h)) + pad,
  };
}
