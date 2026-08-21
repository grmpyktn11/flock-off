// EXPO_PUBLIC_ variables are inlined at build time, so this is a constant
// once the bundle is built, not something that can change at runtime.
//
// Unset means use the mock backend. That keeps a checkout with no
// configuration working offline, and makes talking to a real server an
// explicit choice rather than an accident.
export const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "";

export const USE_MOCK_BACKEND = API_BASE_URL === "";

// Long enough for a cold Valhalla call, short enough that a dead server
// does not leave the user watching a spinner.
export const REQUEST_TIMEOUT_MS = 15000;
