# Backend

FastAPI backend for the camera-avoiding navigation app. Implements the
three endpoints from `final-spec.md`.

Each source is real when its credential is configured and mocked
otherwise, so the service runs with no infrastructure at all and each one
can be switched on independently:

| source | switched on by | falls back to |
|---|---|---|
| cameras | `DATABASE_URL` | `app/mock_data.py` |
| avoidance routing | `VALHALLA_URL` | `app/mock_data.py` |
| baseline, ETAs, autocomplete | `GOOGLE_API_KEY` | `app/mock_data.py` |

The test suite pins all three to the mocks, so a populated `.env` cannot
make it assert against live services - or spend money.

## Run

    pip install -r requirements.txt
    uvicorn app.main:app --reload

With no `DATABASE_URL` the service uses mock cameras and needs no
infrastructure. Set it in the repo root `.env` to use the real table:

    DATABASE_URL=postgresql://...

Use Supabase's session pooler rather than the transaction pooler. psycopg
prepares statements and the transaction pooler does not support them.

Interactive docs at http://127.0.0.1:8000/docs

## Test

    pytest

The suite is pinned to the mock camera source, so a `.env` on the machine
does not change what it asserts. `tests/test_postgis.py` is the exception:
it talks to the real database and skips when `DATABASE_URL` is unset.

If a globally installed pytest plugin breaks collection, run
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest`.

## Endpoints

- `GET /search?q=&lat=&lng=&session_token=` - Places Autocomplete proxy,
  lat/lng bias the results toward the driver. Returns suggestions with no
  coordinates: resolving a location costs a Place Details call each, and
  doing that per suggestion per keystroke would be the most expensive
  possible way to run autocomplete.
- `GET /place?place_id=&session_token=` - resolves the chosen suggestion
  to coordinates. Passing back the search's `session_token` closes the
  Google session so the whole burst bills as one.
- `POST /plan` - `{"origin": {"lat", "lng"}, "destination": {"lat", "lng"}}`
- `POST /replan` - `{"current": {"lat", "lng"}, "destination": {"lat", "lng"}}`

Both planning endpoints return the Google Maps deep link, the chosen
waypoints, the cameras one of the two routes actually drove into with an
`avoided` flag, avoided/unavoidable counts, the two ETAs and their delta,
and our route as an encoded polyline for the app's drift detection.

Cameras merely near the trip are left out. The bounding box returns a few
hundred for a Fairfax-sized box, and reporting those would make
`avoided_count` a measure of the search box rather than of any work done.

## Layout

- `app/main.py` - endpoints
- `app/planner.py` - the planning pipeline: cameras, baseline route,
  avoidance route, verification retries, waypoints, deep link
- `app/waypoints.py` - the waypoint picker (spec step 6)
- `app/geo.py` - polyline codec, haversine, point-to-segment, resampling
- `app/cameras.py` - camera lookups, dispatching to PostGIS or the mock
- `app/db.py` - the two SQL queries against the cameras table
- `app/models.py` - the `Camera` type both sources build
- `app/config.py` - reads the repo root `.env`, picks the camera source
- `app/mock_data.py` - everything that is still a stand-in

## What the dead zone check can and cannot tell you yet

Against PostGIS, verification is `ST_Intersects` on the stored dead zone,
which is directional: a camera pointed away from the driver does not see
them. That is a real improvement on the mock's radius, which flags any
camera near the line regardless of where it is facing.

It does not yet produce meaningful counts, because the routes are still
mocked. A dead zone is a 75ft slice of road buffered to road width, about
23m by 7m, and the mock router draws straight lines between two points.
A straight line does not lie on the road, so it misses the polygons and
every trip reports zero cameras. The SQL is verified directly instead, in
`tests/test_postgis.py`. Real counts arrive with Valhalla, not before.

## Waypoint picker

Google Maps deep links take at most 9 waypoints, so the picker chooses the
few points that hold our detour:

1. Resample our route every 100m.
2. Measure each sample's distance to Google's baseline route.
3. Group runs of samples more than 60m off the baseline into divergence spans.
4. Keep the 9 spans closest to a camera we are avoiding, back in travel order.
5. Per span, take the sample furthest from the baseline - the point Google
   is least likely to shortcut past.
6. Validate by routing through the picks; any span Google still skips gets
   its waypoint moved to the middle of the span, up to 2 attempts.
