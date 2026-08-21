# Mobile app

React Native + Expo (SDK 54). Plans a camera-avoiding route, hands it to
Google Maps, and watches from the background to warn about cameras the
route could not avoid.

## What is here

**Planning.** A search screen with autocomplete, and a plan screen showing
what was avoided, what was not, and what the detour costs. "Start in
Google Maps" records the trip and fires the deep link.

**Driving.** A foreground service with background GPS that speaks a
warning as you approach a camera the route could not avoid, and offers a
re-plan by notification if Google takes you somewhere else.

## Layout

| Path | Purpose |
|---|---|
| `src/api/index.ts` | The only module screens import. Picks the real client or the mock. |
| `src/api/client.ts` | HTTP client. Maps the backend's snake_case and seconds. |
| `src/api/mockBackend.ts` | Used when `EXPO_PUBLIC_API_URL` is unset. |
| `src/lib/drift.ts` | When the driver has left the route, and whether to say so. |
| `src/lib/alerts.ts` | Which camera to warn about, and when. |
| `src/lib/tripService.ts` | The location task and foreground service. |
| `src/lib/tripStore.ts` | The trip on disk, for the headless task to read. |

`src/lib/` is deliberately free of React and native imports where it can
be, so the decisions worth getting right are plain functions with tests.

## Run

    npm install
    npm start
    npm test

Then open the `exp://<lan-ip>:8081` URL in Expo Go. Point it at a backend
with `EXPO_PUBLIC_API_URL`; without one it uses the mock and needs nothing
running.

**The drive-time half does not work in Expo Go.** Background location and
a foreground service both need a development build:

    npx eas build --profile development --platform android

Planning works fine in Expo Go. Starting a trip will not.

## Decisions worth knowing

- **Pinned to Expo SDK 54, not the latest.** The test phone's Expo Go
  supports 54 only. Moving up later is a version bump, not a code change.
- **`overrides` in `package.json`** pins react and react-native.
  NativeWind's `react-native-css-interop` peer-depends on reanimated, and
  without it npm quietly pulled a second copy of RN into the tree.
  `react-native-reanimated` and `react-native-worklets` are direct
  dependencies for that reason, not because app code uses them.
- **`className` only on core `View` and `Text`.** NativeWind 4 does not
  apply classes to third-party components without `cssInterop`, so Paper
  components use their own props or sit inside a styled `View`.
- **Bottom buttons use `useSafeAreaInsets()`**, so they clear the Android
  navigation bar on both gesture and three-button nav.
- **No `android/` folder.** It is generated at prebuild or EAS build time.
