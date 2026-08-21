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

### Deferred: live rerouting

The spec's per-trip flow has a foreground service, background GPS,
proximity alerts and drift detection with a one-tap re-plan. None of the
client side is built, and it is deliberately not being built yet.

`POST /replan` exists and works - it is a fresh plan from the driver's
current position - so the backend is ready whenever the client is.

It is deferred because the thing that decides its shape is unanswered:
whether Google keeps the waypoints after a missed turn or a traffic
reroute. If it drops them reliably, drift fires constantly and re-planning
becomes the main event rather than a fallback, which is a different app.
Answering it needs a real drive, not a tapped link.

When it is built, gate the prompt on `avoided_count`: if a re-plan from
the current position avoids no cameras, Google's path is already fine and
the driver should not be interrupted. The pipeline computes that number
already.

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
