# Backend

FastAPI service. Each data source is real when its credential is set and
mocked otherwise:

| source | switched on by | falls back to |
|---|---|---|
| cameras | `DATABASE_URL` | `app/mock_data.py` |
| avoidance routing | `VALHALLA_URL` | `app/mock_data.py` |
| baseline, ETAs, autocomplete | `GOOGLE_API_KEY` | `app/mock_data.py` |

## Run

    pip install -r requirements.txt
    uvicorn app.main:app --reload

Credentials go in the repo root `.env`. For Supabase use the session
pooler, not the transaction pooler (psycopg prepares statements).

Interactive docs: http://127.0.0.1:8000/docs

## Test

    pytest

The suite pins every source to its mock, so it costs nothing and needs no
credentials. `tests/test_postgis.py` talks to the real database and skips
without `DATABASE_URL`.

If a global pytest plugin breaks collection:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest`

## Endpoints

- `GET /search?q=&lat=&lng=&session_token=` - autocomplete proxy. Returns
  no coordinates; resolve the chosen one via `/place`.
- `GET /place?place_id=&session_token=` - resolves a suggestion to
  coordinates. Reuse the search's `session_token` so Google bills the
  burst as one session.
- `POST /plan` - `{"origin": {"lat", "lng"}, "destination": {"lat", "lng"}}`
- `POST /replan` - `{"current": {"lat", "lng"}, "destination": {"lat", "lng"}}`

Plan responses carry the deep link, waypoints, cameras with an `avoided`
flag, avoided/unavoidable counts, both ETAs and their delta, and the
route polyline. Cameras merely near the trip are excluded.

## Layout

- `app/main.py` - endpoints
- `app/planner.py` - the pipeline: cameras, baseline, avoidance route, waypoints, deep link
- `app/waypoints.py` - waypoint picker
- `app/geo.py` - polyline codec, haversine, resampling
- `app/cameras.py` - camera lookups (PostGIS or mock)
- `app/db.py` - SQL against the cameras table
- `app/config.py` - env config
- `app/mock_data.py` - the mocks

## Waypoint picker

Google Maps deep links take at most 9 waypoints. The picker:

1. Resamples our route every 100m.
2. Measures each sample's distance to Google's baseline.
3. Groups samples more than 60m off the baseline into divergence spans.
4. Keeps the 9 spans closest to a camera, back in travel order.
5. Per span, picks the sample furthest from the baseline.
6. Validates by routing through the picks with Google. Any span Google
   skips gets its waypoint moved to the span middle, up to 2 attempts.

The check for "did the route pass a camera" is `ST_Intersects` between
the route linestring and each camera's stored dead zone polygon. It is
directional: a camera pointed away does not flag. The mock uses a plain
radius and over-flags.
