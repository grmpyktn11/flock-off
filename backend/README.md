# Backend

FastAPI backend for the camera-avoiding navigation app. Implements the
three endpoints from `final-spec.md`.

The cameras table, Valhalla, Google Directions and Google Places are all
mocked in `app/mock_data.py` with sample data for the Fairfax / Herndon
area, so this service builds and tests on its own. Wiring up the real
services means replacing that one module.

## Run

    pip install -r requirements.txt
    uvicorn app.main:app --reload

Interactive docs at http://127.0.0.1:8000/docs

## Test

    pytest

If a globally installed pytest plugin breaks collection, run
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest`.

## Endpoints

- `GET /search?q=&lat=&lng=` - Places Autocomplete proxy, lat/lng bias the
  results toward the driver.
- `POST /plan` - `{"origin": {"lat", "lng"}, "destination": {"lat", "lng"}}`
- `POST /replan` - `{"current": {"lat", "lng"}, "destination": {"lat", "lng"}}`

Both planning endpoints return the Google Maps deep link, the chosen
waypoints, every camera in the trip's bounding box with an `avoided` flag,
avoided/unavoidable counts, the two ETAs and their delta, and our route as
an encoded polyline for the app's drift detection.

## Layout

- `app/main.py` - endpoints
- `app/planner.py` - the planning pipeline: cameras, baseline route,
  avoidance route, verification retries, waypoints, deep link
- `app/waypoints.py` - the waypoint picker (spec step 6)
- `app/geo.py` - polyline codec, haversine, point-to-segment, resampling
- `app/mock_data.py` - everything that is a stand-in for a real service

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
