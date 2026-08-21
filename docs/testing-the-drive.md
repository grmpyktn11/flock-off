# Testing the drive-time features

The planning half is easy to check: call `/plan` and read the numbers.
The driving half is not. It only runs while the app is backgrounded, in a
moving car, with Google Maps in front — which is an expensive place to
find a bug.

So it is tested in four layers, each cheap and each blind to something
the next one catches. Work up them in order; every layer you skip is a
class of bug that survives to the car.

## 1. Unit tests

    cd mobile && npm test

Covers the decisions: when a driver counts as off route, which camera to
warn about and how far out, whether a re-plan is worth interrupting for.
These are plain functions with no React and no native imports, which is
why `src/lib/` is kept that way.

**Blind to:** everything about actually running on a phone.

## 2. Simulated drive, in the app

In a development build, the plan screen has **Simulate drive** and
**Simulate wrong turn**. They replay the planned route through
`handleLocation`, the same function the GPS task calls, at 60x speed.

This is the layer that catches most of it. Real: text-to-speech through
the speaker, the notification and its action, the trip store surviving
across ticks, the re-plan network call, the cooldown and the per-trip cap.

What to expect:

- **Simulate drive** on a route with unavoidable cameras: one spoken
  warning per camera as you pass it, and no repeats.
- **Simulate wrong turn**: the route is followed, then pushed 300m
  sideways. After three ticks off route a re-plan is requested. A
  notification appears *only if* the re-plan avoids a camera — if it does
  not, silence is the correct behaviour, not a bug. Tapping **Re-plan**
  should open Google Maps with a new route.

**Blind to:** whether Android delivers locations to a backgrounded task,
whether the foreground service survives the screen locking or the app
being swapped out, and battery cost.

## 3. Mock location, on the device, stationary

Turn on Developer Options, set **Select mock location app** to a route
player such as Lockito, draw a route through a camera, and play it while
flock-off runs in the background with Google Maps in front.

This is the first layer that exercises the real thing: `expo-location`
delivering to a headless task, the foreground service notification,
Android's background location permission actually being honoured.

Check the foreground service notification stays up, warnings still fire
with the screen off, and nothing dies when you switch apps.

**Blind to:** GPS noise, tunnels, losing signal, what the warnings sound
like over road noise, and whether the timing feels right at speed.

## 4. Drive it

One of the corridors in [premise-test.md](premise-test.md). Take a
passenger to watch the phone.

Four things only this can answer:

1. **Do the warnings arrive usefully early?** The radius is fifteen
   seconds of travel, clamped 150–600m. That number is a guess and this
   is the only way to check it.
2. **Does Google keep the waypoints through a reroute?** Miss a turn on
   purpose. Assumed yes, never measured — and if it is wrong the failure
   is silent, because the plan screen keeps reporting cameras avoided
   while you drive past them.
3. **Do waypoints announce as stops?** If Google says "Stop 1 of 2" on a
   road nobody is stopping at, the picker should prefer fewer waypoints.
   `MAX_WAYPOINTS` is 9; real trips have needed 0–4.
4. **What does it cost in battery?** A foreground service with high
   accuracy GPS on a two second tick is not free.

Record what you find in [premise-test.md](premise-test.md).

## Backend, against real services

    cd backend && pytest

The suite pins every source to its mock, so it never reaches the database,
Valhalla or Google — it costs nothing and works with no credentials.
`tests/test_postgis.py` is the exception and skips without `DATABASE_URL`.

To exercise the real pipeline, set the credentials in `.env` and plan a
trip. What good looks like is in
[adding-a-region.md](adding-a-region.md#4-check-it).
