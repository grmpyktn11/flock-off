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

The three pieces were built in parallel worktrees against mocks and have
not been integrated. Each is verified standalone; nothing is wired
end to end yet. Read the handoffs before changing anything - they carry
the decisions and the known gaps.

Two open items gate real integration work:

1. The waypoint picker has never produced a waypoint. A live `/plan` call
   returned six avoided cameras, zero waypoints, and a deep link with no
   `waypoints=` parameter - an ordinary Google route that avoids nothing.
2. Nobody has confirmed a Google Maps deep link actually holds its
   waypoints around a known camera. That handoff is the premise of the
   project.

The app/backend response contract also disagrees: the app expects
camelCase and minutes, the backend emits snake_case and seconds. The
agreed resolution is that the backend keeps snake_case and seconds and
the app maps in `mobile/src/api/`.

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
