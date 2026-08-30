# Adding a region

One entry in `regions.json`, two commands. No code changes.

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

- `bbox` is `[south, west, north, east]`. It must cover everywhere a
  detour might route through, not just the city. Err generous.
- `osm_extracts`: every Geofabrik state file the box touches. Overlap is
  fine; they get clipped and merged.

## 2. Load the cameras

Dry run first:

    cd ingestion
    python -m ingestion.ingest --region austin --out austin.geojson

Then for real:

    python -m ingestion.ingest --region austin --database-url "$DATABASE_URL"

Idempotent. Cameras that vanish from OSM are marked inactive, not
deleted. Check the count looks plausible: OSM coverage varies by area.

## 3. Build the routing tiles

    python infra/valhalla/build_tiles.py --region austin --work C:/valhalla

About 10 minutes for a DMV-sized region, 1.5 GB RAM, 3 GB scratch disk.
Output is one `valhalla_tiles.tar`. Do not point `--work` at OneDrive or
any synced folder. Details in `infra/valhalla/build_tiles.md`.

## 4. Check it

    python infra/valhalla/smoke_test.py --port 8003 --from <lat,lng> --to <lat,lng>

Pick two points a few km apart with a camera between them. Then plan a
trip:

    cd backend && uvicorn app.main:app --reload
    curl -X POST localhost:8000/plan -H 'content-type: application/json' \
      -d '{"origin":{"lat":..,"lng":..},"destination":{"lat":..,"lng":..}}'

Good: a handful of cameras, an ETA delta of a few minutes. Bad: hundreds
of cameras or a 20 minute delta, which usually means the bbox is too
tight and the router has nowhere to detour.

## Multiple regions

The backend is not region-aware and does not need to be: `/plan` queries
by trip bounding box, so one database serves every region. Valhalla is
the limit: one container per tile set. A second region means a second
container, which the backend does not support yet.
