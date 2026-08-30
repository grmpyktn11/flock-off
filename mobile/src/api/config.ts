// EXPO_PUBLIC_ variables are inlined at build time, so this is a constant
// once the bundle is built, not something that can change at runtime.
//
// Unset means use the mock backend. That keeps a checkout with no
// configuration working offline, and makes talking to a real server an
// explicit choice rather than an accident.
export const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "";

export const USE_MOCK_BACKEND = API_BASE_URL === "";

// Sent as X-App-Key on every request. Not a secret in any real sense - it
// ships inside this bundle and anyone can unzip an APK - but the backend
// refuses callers without it, which turns away the scanners that find an
// open endpoint and go no further. Unset means the backend is running
// without a key too, which is the local development case.
export const APP_KEY = process.env.EXPO_PUBLIC_APP_KEY ?? "";

// Long enough for a cold Valhalla call, short enough that a dead server
// does not leave the user watching a spinner.
export const REQUEST_TIMEOUT_MS = 15000;

// Planning and explanations are legitimately slow: a plan is several
// Google and database round trips (measured at ~15s with Valhalla down),
// and a batch of uncached explanations is a Claude call per camera. 15s
// aborts real work at the finish line, so they get a longer leash.
export const SLOW_REQUEST_TIMEOUT_MS = 60000;
