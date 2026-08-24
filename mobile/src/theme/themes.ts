// The two looks the app can wear, chosen once at first launch.
//
// "standard" is the app as it has always been. "ghost" is the terminal:
// matrix green on near-black, everything monospace, for the user who
// wants the surveillance map to look like what it is. The choice is
// cosmetic only - every token here is a color or a font, and nothing
// downstream is allowed to behave differently by theme.

import {
  MD3DarkTheme,
  MD3LightTheme,
  configureFonts,
} from "react-native-paper";
import {
  DarkTheme as NavDarkTheme,
  DefaultTheme as NavLightTheme,
  Theme as NavTheme,
} from "@react-navigation/native";
import { Platform } from "react-native";

export type ThemeName = "standard" | "ghost";

export type Tokens = {
  name: ThemeName;
  background: string;
  surface: string;
  border: string;
  text: string;
  textMuted: string;
  accent: string;
  /** Monospace family in ghost mode, undefined otherwise. */
  fontFamily: string | undefined;
  /** For expo-status-bar, which wants the foreground color. */
  statusBar: "auto" | "light";
  paper: typeof MD3LightTheme;
  nav: NavTheme;
};

const MONO = Platform.select({ ios: "Menlo", default: "monospace" });

// Matrix palette. The green is the classic phosphor #00FF41 for accents,
// pulled down to a readable #9BE8AD for body text - full-brightness green
// body text on black vibrates and tires the eyes in about a minute.
const GHOST = {
  background: "#000000",
  surface: "#001A08",
  border: "#00A82D",
  text: "#33FF66",
  textMuted: "#1E9940",
  accent: "#00FF41",
};

const ghostFonts = configureFonts({
  config: { fontFamily: MONO },
});

const ghostPaper = {
  ...MD3DarkTheme,
  // A terminal has no rounded corners.
  roundness: 0,
  fonts: ghostFonts,
  colors: {
    ...MD3DarkTheme.colors,
    primary: GHOST.accent,
    onPrimary: "#00230B",
    primaryContainer: "#00330F",
    onPrimaryContainer: GHOST.text,
    secondary: GHOST.textMuted,
    background: GHOST.background,
    surface: GHOST.surface,
    onSurface: GHOST.text,
    surfaceVariant: "#00240B",
    onSurfaceVariant: GHOST.textMuted,
    outline: GHOST.border,
    elevation: {
      ...MD3DarkTheme.colors.elevation,
      level0: "transparent",
      level1: GHOST.surface,
      level2: "#001F0A",
      level3: "#00240B",
      level4: "#00290D",
      level5: "#002E0F",
    },
  },
};

const ghostNav: NavTheme = {
  ...NavDarkTheme,
  colors: {
    ...NavDarkTheme.colors,
    primary: GHOST.accent,
    background: GHOST.background,
    card: GHOST.surface,
    text: GHOST.accent,
    border: GHOST.border,
  },
};

export const THEMES: Record<ThemeName, Tokens> = {
  standard: {
    name: "standard",
    background: "#FFFFFF",
    surface: "#FFFFFF",
    border: "#E5E7EB", // tailwind gray-200, what the borders always were
    text: "#111827", // gray-900
    textMuted: "#6B7280", // gray-500
    accent: MD3LightTheme.colors.primary,
    fontFamily: undefined,
    statusBar: "auto",
    paper: MD3LightTheme,
    nav: NavLightTheme,
  },
  ghost: {
    name: "ghost",
    ...GHOST,
    fontFamily: MONO,
    statusBar: "light",
    paper: ghostPaper,
    nav: ghostNav,
  },
};
