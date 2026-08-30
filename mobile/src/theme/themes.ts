// The app's one look, matched to the showcase site: cream ground, warm
// surface, olive = the route that works, raspberry = the cameras. One
// accent family per meaning, everywhere. Tokens exist so colors and
// fonts live in a single place rather than scattered through screens;
// nothing downstream is allowed to behave differently by theme.

import { MD3LightTheme, configureFonts } from "react-native-paper";
import {
  DefaultTheme as NavLightTheme,
  Theme as NavTheme,
} from "@react-navigation/native";

export type Tokens = {
  background: string;
  surface: string;
  border: string;
  text: string;
  textMuted: string;
  /** Raspberry: cameras, and only cameras. */
  accent: string;
  /** Raspberry at low opacity, for tinted chips and highlights. */
  accentSoft: string;
  /** Olive: the route that works, cameras avoided, good news. */
  olive: string;
  /** Olive dark enough to carry text. */
  oliveDeep: string;
  /** The site's typeface. Android does not synthesize weights for
   * custom fonts, so each weight is its own family. */
  fontFamily: string | undefined;
  fontFamilySemibold: string | undefined;
  fontFamilyBold: string | undefined;
  /** For expo-status-bar, which wants the foreground color. */
  statusBar: "auto" | "light";
  paper: typeof MD3LightTheme;
  nav: NavTheme;
};

// The site's light palette, verbatim.
const GROUND = "#FFF7EB";
const SURFACE = "#F9F0E0";
const LINE = "#E5D9C3";
const INK = "#29271F";
const INK_MUTED = "#6D675A";
const RASPBERRY = "#CC3A63";
const RASPBERRY_SOFT = "rgba(204, 58, 99, 0.14)";
const OLIVE = "#A2AB73";
const OLIVE_DEEP = "#6F7847";
const BASELINE_GRAY = "#A49C8C";

// Primary is ink, like the site's pill buttons: the strong colors are
// saved for meaning (raspberry = cameras, olive = avoided), so the CTAs
// stay quiet. Paper's elevation tints are re-based on the cream ground
// so raised surfaces warm up instead of going gray.
const FONT = "SpaceGrotesk_400Regular";
const FONT_SEMIBOLD = "SpaceGrotesk_600SemiBold";
const FONT_BOLD = "SpaceGrotesk_700Bold";

const paper: typeof MD3LightTheme = {
  ...MD3LightTheme,
  fonts: configureFonts({ config: { fontFamily: FONT } }),
  colors: {
    ...MD3LightTheme.colors,
    primary: INK,
    onPrimary: GROUND,
    primaryContainer: SURFACE,
    onPrimaryContainer: INK,
    secondary: OLIVE_DEEP,
    onSecondary: GROUND,
    secondaryContainer: "#E4E7D0",
    onSecondaryContainer: "#3A4022",
    tertiary: RASPBERRY,
    onTertiary: GROUND,
    tertiaryContainer: "#F8DCE4",
    onTertiaryContainer: "#5C1129",
    error: RASPBERRY,
    background: GROUND,
    onBackground: INK,
    surface: GROUND,
    onSurface: INK,
    surfaceVariant: SURFACE,
    onSurfaceVariant: INK_MUTED,
    outline: BASELINE_GRAY,
    outlineVariant: LINE,
    inverseSurface: INK,
    inverseOnSurface: GROUND,
    inversePrimary: "#E8DFC9",
    surfaceDisabled: "rgba(41, 39, 31, 0.12)",
    onSurfaceDisabled: "rgba(41, 39, 31, 0.38)",
    backdrop: "rgba(41, 39, 31, 0.4)",
    elevation: {
      level0: "transparent",
      level1: "#FBF3E4",
      level2: SURFACE,
      level3: "#F6ECD8",
      level4: "#F4E9D3",
      level5: "#F2E6CD",
    },
  },
};

const nav: NavTheme = {
  ...NavLightTheme,
  colors: {
    ...NavLightTheme.colors,
    primary: INK,
    background: GROUND,
    card: GROUND,
    text: INK,
    border: LINE,
    notification: RASPBERRY,
  },
};

export const TOKENS: Tokens = {
  background: GROUND,
  surface: SURFACE,
  border: LINE,
  text: INK,
  textMuted: INK_MUTED,
  accent: RASPBERRY,
  accentSoft: RASPBERRY_SOFT,
  olive: OLIVE,
  oliveDeep: OLIVE_DEEP,
  fontFamily: FONT,
  fontFamilySemibold: FONT_SEMIBOLD,
  fontFamilyBold: FONT_BOLD,
  statusBar: "auto",
  paper,
  nav,
};
