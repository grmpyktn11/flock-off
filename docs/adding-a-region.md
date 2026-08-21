# Adding a region

Everything the project knows about where it operates lives in one file,
`regions.json` at the repo root. Adding a city is an entry there plus two
commands. No code changes.

## 1. Describe the region

```json
"austin": {
  "description": "Austin and the surrounding metro.",
  "bbox": [30.05, -98.05, 30.60, -97.45],
  "osm_extracts": [
    "https://download.geofabrik.de/north-america/us/texas-latest.osm.pbf"
  ]
}
```

**bbox** is `[south, west, north, east]` in degrees. It bounds the camera
query and clips the routing tiles, so it has to cover everywhere a trip
might route *through*, not just the city. A detour around a camera can
leave the city limits; if it leaves the bounding box, there are no roads
out there to route on. Err generous - the cost is roughly linear and the
DMV region, four states' worth of box, is a 1.4 MB table.

**osm_extracts** are the Geofabrik downloads the routing tiles are built
from. List every state or country the box touches. They get clipped to the
bbox and merged, so overlap is fine and being generous is cheap. Browse
them at <https://download.geofabrik.de>.

## 2. Load the cameras

```
cd ingestion
python -m ingestion.ingest --region austin --database-url "$DATABASE_URL"
```

Pulls ALPR and speed camera nodes from OpenStreetMap, snaps each to the
road it watches, computes its dead zone, and upserts. Idempotent: run it
again and only `last_seen` moves. Cameras that vanish from OSM are marked
inactive rather than deleted, so a removed camera stays distinguishable
from one never seen.

Do a dry run first to see what is there, without touching the database:

```
python -m ingestion.ingest --region austin --out austin.geojson
```

**Coverage varies enormously by area.** OSM camera data is contributed by
people, so a thin count means thin mapping, not an absence of cameras.
Northern Virginia has 2,872 because the community mapped them. Check the
count looks plausible for the area before trusting a route.

## 3. Build the routing tiles

```
python infra/valhalla/build_tiles.py --region austin --work C:/valhalla
```

Downloads, clips, merges and starts the build. Takes about ten minutes
for a region the size of the DMV, needs roughly 1.5 GB of RAM and 3 GB of
scratch disk, and produces one `valhalla_tiles.tar` to ship to the server.

Do not point `--work` inside OneDrive or any synced folder.

Details, measurements and what to do when a build goes wrong are in
[../infra/valhalla/build_tiles.md](../infra/valhalla/build_tiles.md).

## 4. Check it

```
python infra/valhalla/smoke_test.py --port 8003 --from <lat,lng> --to <lat,lng>
```

Routes across the region, drops a real dead zone from the ingestion code
onto that route, re-routes with it excluded, and asserts the first route
crosses the polygon and the second does not. Pick two points a few
kilometres apart with a camera between them.

Then plan a real trip and read the numbers:

```
cd backend && uvicorn app.main:app --reload
curl -X POST localhost:8000/plan -H 'content-type: application/json' \
  -d '{"origin":{"lat":..,"lng":..},"destination":{"lat":..,"lng":..}}'
```

What good looks like: a handful of cameras reported rather than hundreds,
an ETA delta of a few minutes rather than twenty, and waypoints only on
trips that avoided something. If a trip reports many cameras or a large
delta, the bounding box is probably too tight and the router has nowhere
to detour to.

## Serving more than one region

Nothing in the backend is region-aware, and it does not need to be. The
cameras table is global: `/plan` queries by the trip's own bounding box,
so a database holding several regions serves all of them with no changes.

Valhalla is the limit. One container serves one tile set, so a second
region means a second container and a `VALHALLA_URL` per region - which
is the point at which the backend would need to learn which is which.
That does not exist yet, and should not be built until a second region
actually runs.
