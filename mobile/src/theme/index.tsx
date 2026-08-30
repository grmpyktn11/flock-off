// One theme, one hook. The provider indirection stays so screens keep
// reading tokens from a single place.

import { ReactNode, createContext, useContext } from "react";

import { TOKENS, Tokens } from "./themes";

type ThemeState = {
  tokens: Tokens;
};

const ThemeContext = createContext<ThemeState>({ tokens: TOKENS });

export function useAppTheme(): ThemeState {
  return useContext(ThemeContext);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <ThemeContext.Provider value={{ tokens: TOKENS }}>
      {children}
    </ThemeContext.Provider>
  );
}
