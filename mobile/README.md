# Mobile app

React Native + Expo (SDK 54). Plans a camera-avoiding route, hands it to
Google Maps, and warns from the background about cameras the route could
not avoid.

## Run

    npm install
    npm start
    npm test

Open the `exp://` URL in Expo Go. Set `EXPO_PUBLIC_API_URL` to use a real
backend; unset, the app uses its own mock and needs nothing running.

Planning works in Expo Go. Driving does not: background location and the
foreground service need a development build:

    npx eas build --profile development --platform android

## Layout

| Path | Purpose |
|---|---|
| `src/api/index.ts` | The only module screens import. Real client or mock. |
| `src/api/client.ts` | HTTP client. |
| `src/api/mockBackend.ts` | Used when `EXPO_PUBLIC_API_URL` is unset. |
| `src/lib/drift.ts` | Off-route detection. |
| `src/lib/alerts.ts` | Which camera to warn about, and when. |
| `src/lib/tripService.ts` | Location task and foreground service. |
| `src/lib/tripStore.ts` | Trip on disk for the headless task. |

`src/lib/` avoids React and native imports so the logic is plain
functions with tests.

## Gotchas

- Pinned to Expo SDK 54. The test phone's Expo Go supports 54 only.
- `overrides` in `package.json` pins react and react-native; without it
  npm pulls a second copy of RN via NativeWind's peer deps.
- `className` works only on core `View` and `Text`. Paper components use
  their own props.
- Bottom buttons use `useSafeAreaInsets()` to clear the Android nav bar.
- No `android/` folder. It is generated at build time.
