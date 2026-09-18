// The values the server and the browser must agree on, fetched rather than retyped.
// Top-level await, so every importer sees them resolved before any app code runs.

const served = await fetch('/api/config').then((r) => r.json());

export const DISPLAY_NAME = served.displayName;
export const MIN_SCALE = served.minScale;
export const MAX_SCALE = served.maxScale;
export const MIN_BOX_WIDTH = served.minBoxWidth;
export const MAX_BOX_WIDTH = served.maxBoxWidth;
export const MIN_SELECTION_CHARS = served.minSelectionChars;
export const CHROME_HEIGHT = served.chromeHeight;
export const BOX_GAP = served.boxGap;
export const STILL_RUNNING_MESSAGE = served.stillRunningMessage;
export const MAX_INSTRUCTIONS_CHARS = served.maxInstructionsChars;

// Statuses that mean a run has not settled yet.
export const UNFINISHED = new Set(served.unfinished);

// The stylesheet needs the chrome height as well, and cannot fetch it itself.
// Handed over here so config.py stays the one owner of the number.
document.documentElement.style.setProperty('--chrome-h', `${CHROME_HEIGHT}px`);
