# Testing the drive-time features

The driving half only runs backgrounded, in a moving car, with Google
Maps in front. Test it in four layers, in order. Each layer is blind to
something the next one catches.

## 1. Unit tests

    cd mobile && npm test

Covers drift detection, warning selection, replan decisions. Plain
functions, no phone.

## 1b. Replay a real plan

    cd backend && uvicorn app.main:app --port 8000
    cd mobile  && TEST_API_URL=http://127.0.0.1:8000 npm test

Fetches a real plan and drives the whole route through the drift and
alert logic. Catches what synthetic straight lines miss: real routes
bend. Skipped without `TEST_API_URL`.

## 2. Simulated drive, in the app

In a development build, the plan screen has **Simulate drive** and
**Simulate wrong turn**. They replay the route through `handleLocation`
at 60x. Real: text-to-speech, notifications, the trip store, the replan
call.

Expected:

- Simulate drive: one spoken warning per unavoidable camera, no repeats.
- Simulate wrong turn: after three ticks off route a replan fires. A
  notification appears only if the replan avoids a camera. Silence
  otherwise is correct.

## 3. Mock location on the device

Developer Options > Select mock location app > a route player like
Lockito. Draw a route through a camera, play it with flock-off
backgrounded and Google Maps in front.

Check: the foreground service notification stays up, warnings fire with
the screen off, nothing dies on app switch.

## 4. Drive it

Take a passenger. Only this answers:

1. Do warnings arrive usefully early? (15s of travel, clamped 150-600m,
   currently a guess.)
2. Does Google keep the waypoints through a reroute? Miss a turn on
   purpose. If it drops them, the failure is silent.
3. Do waypoints announce as stops in Google Maps?
4. What does GPS on a 2s tick cost in battery?

## Backend against real services

    cd backend && pytest

The suite pins everything to mocks and costs nothing.
`tests/test_postgis.py` skips without `DATABASE_URL`. To exercise the
real pipeline, fill `.env` and plan a trip; what good looks like is in
[adding-a-region.md](adding-a-region.md#4-check-it).

## Status (2026-08-21)

Seen working in Expo Go on live services: search, plan, handover, Google
driving through our waypoint, spoken warnings firing once each.

Not yet seen (needs a development build): background location delivery,
the foreground service surviving screen lock, the replan notification,
anything at real speed in a real car.
