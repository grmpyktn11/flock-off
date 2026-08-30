# Releasing

## The two permanent things

- **The signing key.** Android refuses updates signed by a different key.
  Lose it and you can never update the app. EAS holds it; back it up:
  `eas credentials` > Android > download the keystore. If you publish to
  Play, enroll in Play App Signing.
- **The package name** (`com.flockoff.app`). Changing it makes a
  different app.

## Distribution

- **Direct APK:** send the file, they enable "install unknown apps". No
  review, no fee. No auto-updates unless OTA is set up. Right for
  testers.
- **Google Play:** $25 once. Use the internal testing track first: up to
  100 emails, near-instant review, real auto-updating installs.

## What Play requires

- A publicly hosted privacy policy ([docs/privacy.md](privacy.md) on
  GitHub Pages works).
- A Data safety declaration matching reality: location is used on-device
  for warnings, never sent; the server only receives origin and
  destination.
- Background location approval (below).
- A recent target SDK (Expo SDK 54 is fine).
- Store listing: icon, screenshots, descriptions, content rating.

## Background location

`ACCESS_BACKGROUND_LOCATION` needs a declaration form, a video of the
feature working, and evidence the app works without it. Budget real time
for this; it is the likeliest delay.

The case: the app warns while Google Maps is in the foreground doing
navigation, so foreground-only location cannot work. Declining the
permission still gives you the route; you lose spoken warnings and the
app says so.

Framing matters: describe it as a route planner that gives drivers a
choice about being photographed, not as evading anything. Avoiding
cameras is legal and camera-warning apps have been on Play for years,
but reviewers read the listing first.

## Versions

- `version` (app.json): what humans see.
- `versionCode`: must increase every upload. `autoIncrement` is on in the
  production profile.
- `runtimeVersion`: set to the `appVersion` policy so a JS update only
  reaches builds of the same app version.

## OTA updates

`expo-updates` is installed and configured. Push JS changes without a
rebuild:

    npx eas update --branch preview --message "what changed"

Ships anything in `src/`. Cannot ship native libraries, permissions, the
icon, or the name.

## Build profiles

- **development**: loads JS from Metro. For your desk.
- **preview**: standalone APK. For testers and driving.
- **production**: .aab for Play.

## The classic mistake

`EXPO_PUBLIC_API_URL` is frozen at build time. A preview APK built
pointing at your LAN IP works on your wifi and nowhere else. Deploy the
backend to a public address first. See [deploying.md](deploying.md).
