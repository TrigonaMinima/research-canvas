// The values the server and the browser must agree on, fetched rather than retyped.
// Top-level await, so every importer sees them resolved before any app code runs.

const served = await fetch('/api/config').then((r) => r.json());

export const DISPLAY_NAME = served.displayName;
export const MIN_SCALE = served.minScale;
export const MAX_SCALE = served.maxScale;
export const MIN_BOX_WIDTH = served.minBoxWidth;
export const MAX_BOX_WIDTH = served.maxBoxWidth;
export const MIN_SELECTION_CHARS = served.minSelectionChars;
export const STILL_RUNNING_MESSAGE = served.stillRunningMessage;

// Statuses that mean a run has not settled yet.
export const UNFINISHED = new Set(served.unfinished);
