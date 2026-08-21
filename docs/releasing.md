# Releasing

Everything between "it works on my phone" and other people using it.

## The one thing you cannot undo

**The signing key.** Every Android app is cryptographically signed. Android
refuses to install an update signed by a different key than the version
already on the phone - that is the whole security model, and it stops
someone shipping a malicious "update" to your app.

Lose the key and you cannot update your own app. Ever. Not by appealing,
not by proving ownership. Users have to uninstall and install a
differently-named app, losing everything.

EAS generated one for you and holds it. Two things follow:

- Back it up: `eas credentials`, Android, download the keystore, and keep
  it somewhere that is not only this laptop.
- If you later publish to Play, enrol in Play App Signing, where Google
  holds the key and can help you recover.

The **package name** - `com.flockoff.app` - is the other permanent thing.
It identifies the app forever. Changing it makes a different app.

## Two ways to give people the app

### Direct APK

Send them a file. They enable "install unknown apps" and install it. No
store, no review, no fee, no rules.

Right for: you, friends, early testers. This is where you are.

Costs: no auto-updates unless you set up OTA (below), a scary
"unknown sources" warning, and no discovery.

### Google Play

$25 once, forever. Auto-updates, trust, discoverability - and review.

Play has four tracks, and they matter:

| Track | Who sees it | Review |
|---|---|---|
| Internal testing | Up to 100 emails you list | Minutes, minimal |
| Closed testing | A list or group you invite | Fuller |
| Open testing | Anyone with the link | Full |
| Production | Everyone | Full, strictest |

Internal testing is the cheat code: near-instant, and it gives testers
real auto-updating installs without the sideloading warning.

## What Play requires that sideloading does not

**A privacy policy, publicly hosted.** Mandatory for anything touching
location. A GitHub Pages page is fine.

**A Data safety declaration.** You state what you collect and why, and it
must match reality. flock-off's honest answer is unusually good: precise
location is used on the device to warn about cameras and is never sent
anywhere; the backend only ever receives an origin and a destination, and
no account identifies who asked.

**Background location approval - the hard one.** See below.

**A recent target SDK.** Google requires new apps to target an API level
within about a year of the current one, and raises it annually. Expo SDK
54 already does; it becomes a chore later, not now.

**Store listing.** Icon, screenshots, short and full description, content
rating questionnaire.

## Background location: the real obstacle

`ACCESS_BACKGROUND_LOCATION` is the most heavily scrutinised permission
on Play. Google requires:

1. A declaration form explaining why the feature cannot work with
   foreground location only.
2. **A video** showing the feature actually working.
3. Evidence the app is useful without it.

Apps get rejected here routinely, usually for asking without a
user-visible reason.

flock-off's case is genuinely strong, and worth writing in these terms:
the app warns a driver about cameras the route could not avoid, while
Google Maps is in the foreground doing the navigation. Foreground-only
location cannot work, because by design this app is not the app on
screen. The warnings are the entire feature.

It also declines gracefully. Refuse the permission and you still get the
camera-avoiding route; you lose the spoken warnings and the app says so.
That is exactly what Google wants to see.

Budget real time for this. It is the single most likely thing to delay a
Play release, and none of it applies to sideloading.

## A policy question worth thinking about early

The app plans routes around automated licence plate readers and speed
cameras. Both are legal to avoid: choosing which public road to drive on
is not an offence anywhere in the US, and speed camera warning apps have
been on Play for years.

But reviewers read a listing before they read a codebase. Describe it as
what it is - a route planner that gives drivers a choice about being
photographed - and not as evading anything. The framing costs nothing and
a rejection costs weeks.

## Versions

Three numbers, easily confused:

- **`version`** (`1.0.0` in app.json) - what humans see.
- **`versionCode`** - an integer Android compares to decide what counts as
  an update. It must increase every upload. `eas.json` has
  `autoIncrement` on the production profile, so EAS handles it.
- **`runtimeVersion`** - which builds a given OTA update is compatible
  with. Set to the `appVersion` policy, so a JS update only reaches builds
  of the same app version. That is the safe default: it stops new
  JavaScript landing on a binary that lacks a native module it needs.

## Over-the-air updates

`expo-updates` lets you push new JavaScript to installed apps without a
rebuild or a store review. Fixes reach people on next launch.

**Set this up before you distribute anything.** It needs a native module
compiled in, so adding it later means rebuilding and redistributing every
copy already handed out.

What it can ship: anything in `src/` - logic, screens, copy, thresholds.
What it cannot: a new native library, permissions, the icon, the name.
Those still need a build.

## The build profiles

`eas.json` defines three:

- **development** - loads JS from Metro. For you, at a desk.
- **preview** - standalone APK with the JS baked in. For testers, and for
  driving, where there is no Metro.
- **production** - an app bundle (.aab) for Play, which requires that
  format rather than an APK.

## One thing that will catch you

`EXPO_PUBLIC_API_URL` is frozen at build time. A preview APK built while
it points at `192.168.1.190` works on your home wifi and nowhere else.

Before building anything for someone else, the backend needs a public
address. That means deploying it - see the VPS notes in the ingestion
handoff for sizing. Measured on the DMV tile set: Valhalla holds 597 MiB
resident and FastAPI about 35 MB, so a 2 GB box is workable and 4 GB is
comfortable.
