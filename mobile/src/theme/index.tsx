// Which theme the app wears, on disk, behind a hook.
//
// Follows the firstRun.ts pattern: storage failures never block anything,
// they just fall back - here to the standard look, plus re-showing the
// picker next launch, which costs one tap.

import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  ReactNode,
  createContext,
  useContext,
  useEffect,
  useState,
} from "react";

import { THEMES, ThemeName, Tokens } from "./themes";

const KEY = "themeName";

type ThemeState = {
  tokens: Tokens;
  /** null while loading; false shows the picker; true means chosen. */
  chosen: boolean | null;
  choose: (name: ThemeName) => void;
};

const ThemeContext = createContext<ThemeState>({
  tokens: THEMES.standard,
  chosen: null,
  choose: () => {},
});

export function useAppTheme(): ThemeState {
  return useContext(ThemeContext);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [name, setName] = useState<ThemeName | null>(null);
  const [chosen, setChosen] = useState<boolean | null>(null);

  useEffect(() => {
    AsyncStorage.getItem(KEY)
      .then((stored) => {
        if (stored === "standard" || stored === "ghost") {
          setName(stored);
          setChosen(true);
        } else {
          setChosen(false);
        }
      })
      .catch(() => setChosen(false));
  }, []);

  function choose(next: ThemeName) {
    setName(next);
    setChosen(true);
    AsyncStorage.setItem(KEY, next).catch(() => {
      // They will pick again next launch.
    });
  }

  return (
    <ThemeContext.Provider
      value={{ tokens: THEMES[name ?? "standard"], chosen, choose }}
    >
      {children}
    </ThemeContext.Provider>
  );
}
