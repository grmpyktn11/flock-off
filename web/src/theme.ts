// One theme decision, read once at load. The CSS follows the system on
// its own; this is for the parts CSS cannot reach, the basemap and the
// colors painted onto the map canvas.
export const DARK: boolean =
  window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;

export const MAP_STYLE = DARK
  ? "https://tiles.openfreemap.org/styles/dark"
  : "https://tiles.openfreemap.org/styles/positron";
