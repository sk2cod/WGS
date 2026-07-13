// Canvas + safe-zone constants shared by every slide template (Section 6/12).
export const CANVAS_WIDTH = 1080;
export const CANVAS_HEIGHT = 1350; // 4:5

// A 3:4 box centered inside the 4:5 canvas, height-constrained since 3:4's
// width-for-full-height (1350 * 3/4) already fits inside 1080.
export const SAFE_ZONE_WIDTH = Math.round(CANVAS_HEIGHT * (3 / 4)); // 1012
export const SAFE_ZONE_INSET_X = Math.round((CANVAS_WIDTH - SAFE_ZONE_WIDTH) / 2); // 34
