# App shell handoff

Branch: `feature/app-shell`. Scope was the React Native app shell only,
built against a mocked backend so it could proceed in parallel with the
backend and ingestion worktrees.

## What is built

- Expo app with NativeWind (Tailwind) and React Native Paper.
- Search screen: Places-style autocomplete for start and destination.
- Plan screen: avoided camera count, ETA delta, unavoidable camera list.
- Deep link launch: hands the route to Google Maps.
- Mocked `GET /search` and `POST /plan` with Fairfax / Herndon data.

## File map

| File | Purpose |
|---|---|
| `App.tsx` | Providers (Paper, SafeArea) and the two-screen stack |
| `src/api/types.ts` | `Place`, `Camera`, `Plan` - the backend contract |
| `src/api/mockBackend.ts` | Fake `searchPlaces()` and `planRoute()` |
| `src/screens/SearchScreen.tsx` | Autocomplete, 250ms debounce, Plan route button |
| `src/screens/PlanScreen.tsx` | Plan result and Start in Google Maps button |
| `src/lib/googleMaps.ts` | `openInGoogleMaps()` deep link launch |
| `babel.config.js`, `metro.config.js`, `tailwind.config.js`, `global.css` | NativeWind wiring |

## The one thing to settle before merging

`src/api/types.ts` is camelCase (`avoidedCount`, `deepLinkUrl`,
`etaDeltaMinutes`). FastAPI will emit snake_case unless told otherwise.
Pick one side to adapt: response aliases on the backend, or a mapping
layer in the app. Deciding after both sides are written costs more.

The app currently expects this from `POST /plan`:

    {
      deepLinkUrl, origin, destination, cameras[],
      avoidedCount, unavoidableCount,
      baselineEtaMinutes, avoidanceEtaMinutes, etaDeltaMinutes,
      routePolyline
    }

`Camera` is `{ id, type: "alpr" | "speed_camera", lat, lng, avoided }`.
`Place` is `{ placeId, description, lat, lng }`.

## Wiring the real backend

There is no HTTP layer at all right now - no base URL, no fetch, no
retry or error handling, no env config. `src/api/mockBackend.ts` is the
entire backend. Replacing it is a new file implementing the same two
functions, not an edit to the screens. Nothing else in the app touches
the network.

## Decisions worth knowing

- **Pinned to Expo SDK 54, not 57.** The scaffold came up on 57, but the
  test phone's Expo Go supports 54 only. Downgrading was the fast path to
  a device demo. Moving to 57 later is a version bump, not a code change.
- **`overrides` block in `package.json`** pins react and react-native.
  NativeWind's `react-native-css-interop` peer-depends on reanimated;
  without reanimated installed, npm quietly pulled a second copy of RN
  0.86 into the tree. `react-native-reanimated` and `react-native-worklets`
  are direct dependencies for that reason, not because app code uses them.
- **`className` is only used on core RN `View` and `Text`.** NativeWind 4
  does not apply classes to third-party components without `cssInterop`,
  so Paper components use their own props or sit inside a styled `View`.
- **Bottom buttons use `useSafeAreaInsets()`**, not fixed padding, so they
  clear the Android navigation bar on both 3-button and gesture nav.
- **minSdkVersion is the Expo SDK 54 default (24 / Android 7.0).** There
  is no `android/` folder in the repo - it is gitignored and generated at
  prebuild or EAS build time. Overriding needs `expo-build-properties`.

## Not built (out of scope, from the spec's per-trip flow)

- Foreground service and background GPS
- Proximity TTS alerts for unavoidable cameras
- Drift detection and `POST /replan`
- Trip end conditions
- Any auth, caching, or persistence

## Verification status

- `npx expo-doctor`: 18/18 checks pass
- `npx tsc --noEmit`: clean
- `npx expo export --platform android`: bundles without errors
- Both screens confirmed rendering on a physical Android device via Expo Go
- **Not confirmed:** tapping "Start in Google Maps" actually opening Google
  Maps with the waypoints held. Worth one manual tap, since that handoff is
  the core premise of the project.

## Running it

    npm install
    npm start

Then open the `exp://<lan-ip>:8081` URL in Expo Go. There is no emulator
or `adb` on the machine this was built on, so `npm run android` was never
exercised.
