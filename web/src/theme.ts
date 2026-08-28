// Theme state: the toggle wins, localStorage remembers it, the system
// preference is the default. CSS reads data-theme on <html>; the maps
// subscribe here because canvas colors are out of CSS's reach.

const LIGHT_STYLE = "https://tiles.openfreemap.org/styles/positron";
const DARK_STYLE = "https://tiles.openfreemap.org/styles/dark";

function storedTheme(): string | null {
  try {
    return localStorage.getItem("theme");
  } catch {
    return null;
  }
}

const system = window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
let dark = storedTheme() ? storedTheme() === "dark" : system;

const listeners: ((dark: boolean) => void)[] = [];

export function isDark(): boolean {
  return dark;
}

export function mapStyle(): string {
  return dark ? DARK_STYLE : LIGHT_STYLE;
}

export function onThemeChange(listener: (dark: boolean) => void): void {
  listeners.push(listener);
}

export function toggleTheme(): void {
  dark = !dark;
  try {
    localStorage.setItem("theme", dark ? "dark" : "light");
  } catch {
    // Private windows still get the toggle, just not the memory.
  }
  apply();
  for (const listener of listeners) listener(dark);
}

function apply(): void {
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

apply();
