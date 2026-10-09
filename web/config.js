// The values the server and the browser must agree on, fetched rather than retyped.
// Top-level await, so every importer sees them resolved before any app code runs.

const served = await fetch('/api/config').then((r) => r.json());

export const DISPLAY_NAME = served.displayName;
export const HARD_RELOAD_ATTR = served.hardReloadAttr;
export const MIN_SCALE = served.minScale;
export const MAX_SCALE = served.maxScale;
export const MIN_BOX_WIDTH = served.minBoxWidth;
export const MAX_BOX_WIDTH = served.maxBoxWidth;
export const MIN_SELECTION_CHARS = served.minSelectionChars;
export const CHROME_HEIGHT = served.chromeHeight;
export const BOX_GAP = served.boxGap;
export const ANCHOR_LEAD = served.anchorLead;
export const DRAG_SLOP = served.dragSlop;
export const STILL_RUNNING_MESSAGE = served.stillRunningMessage;
export const MAX_INSTRUCTIONS_CHARS = served.maxInstructionsChars;
export const MAX_PRESETS = served.maxPresets;
export const MAX_PRESET_LABEL_CHARS = served.maxPresetLabelChars;
export const MAX_PRESET_QUESTION_CHARS = served.maxPresetQuestionChars;
export const MAX_TITLE_CHARS = served.maxTitleChars;
export const REVIEW_WIDTH = served.reviewWidth;
export const REVIEW_MARGIN = served.reviewMargin;
export const MIN_TOC_HEADINGS = served.minTocHeadings;
export const TOC_MAX_LEVEL = served.tocMaxLevel;
export const BLANK_TOPIC_MESSAGE = served.blankTopicMessage;
export const BRIEF_CRASHED_REASON = served.briefCrashedReason;
export const MAX_TOPIC_CHARS = served.maxTopicChars;
export const MAX_RESEARCH_PROMPT_CHARS = served.maxResearchPromptChars;
export const RESEARCH_PROMPT_TOO_LONG_MESSAGE = served.researchPromptTooLongMessage;

// Statuses that mean a run has not settled yet.
export const UNFINISHED = new Set(served.unfinished);

// The blocks in a body that scroll sideways in place: a sideways wheel over one moves
// it, not the desk.
export const SCROLL_BLOCKS = '.table-wrap, .prose pre, .prose .math.block, .prose .math.amsmath, .prose .math.inline';

// The stylesheet needs the chrome height as well, and cannot fetch it itself.
// Handed over here so config.py stays the one owner of the number.
document.documentElement.style.setProperty('--chrome-h', `${CHROME_HEIGHT}px`);
