# flock-off

Driving navigation that plans routes around Flock ALPR and fixed speed
cameras, then hands the route to Google Maps as waypoints so Google does
the turn-by-turn. Test region: Fairfax / Herndon, Virginia.

The full design is in [docs/final-spec.md](docs/final-spec.md).

## Layout

| Path | What it is |
|---|---|
| `mobile/` | React Native + Expo app (SDK 54). Two screens, currently on a mocked backend. |
| `backend/` | FastAPI service: `/search`, `/plan`, `/replan`, `/health`, plus the waypoint picker. Data sources mocked in `app/mock_data.py`. |
| `ingestion/` | Overpass camera ingestion, dead zone geometry, `ingestion/schema.sql`. Verified against live PostGIS and Valhalla. |
| `infra/valhalla/` | Valhalla tile build docs and smoke test. |
| `docs/handoffs/` | Per-piece handoff notes from the three parallel build sessions. |

## Status

`/plan` runs end to end on real data: live cameras from PostGIS, real dead
zone geometry, real routing from Valhalla, real waypoints in the deep
link. Measured across seven Fairfax corridors, avoiding between 0 and 5
cameras per trip.

Still mocked: Google Places autocomplete and the Google baseline route.
Both need an API key. Until then the baseline comes from Valhalla, which
follows real roads and so gets the camera comparison right, but its ETA is
a placeholder - see [docs/eta-delta.md](docs/eta-delta.md).

The app talks to the backend over HTTP when `EXPO_PUBLIC_API_URL` is set
and falls back to its mock otherwise. It has not been pointed at the real
backend yet.

### Settled

- A Google Maps deep link does hold its waypoints. That was the premise
  of the whole project and it checks out. See
  [docs/premise-test.md](docs/premise-test.md).
- The waypoint picker works. The earlier report that it never produced a
  waypoint was a trip with no camera near the route plus a bug in what
  counted as avoided.
- The response contract: the backend keeps snake_case and seconds, and
  the app maps in `mobile/src/api/`.

### In scope but not built: drive-time alerts

The spec's per-trip flow keeps a foreground service running with
background GPS, and speaks a warning through the car audio when the
driver comes within a speed-adjusted distance of a camera the route could
not avoid. That is still the plan, and it is what the plan screen means
when it says "you will get an audio alert near each one".

It needs no network and no backend: the unavoidable camera list and the
route polyline both arrive in the plan response, and the check is a
haversine distance on each GPS tick.

### Deferred: re-planning after a missed turn

Drift detection and the one-tap re-plan are deferred. See
[docs/todo.md](docs/todo.md).

## Running the pieces

    # backend
    cd backend && pip install -r requirements.txt
    uvicorn app.main:app --reload
    pytest

    # ingestion (offline, bundled fixtures)
    cd ingestion && pip install -r requirements.txt
    python -m ingestion.ingest --cameras-file ingestion/sample_cameras.json
    python -m pytest tests -q

    # mobile
    cd mobile && npm install && npm start
